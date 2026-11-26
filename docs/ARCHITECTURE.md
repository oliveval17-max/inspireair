# Architecture InspireAir

## Vue d'ensemble

```
inspireair/
├── src/inspireair/        le noyau (libre de GUI)
│   ├── model.py           modèle de preset (dataclasses, validation, describe())
│   ├── schema/            schéma JSON (validation des fichiers de preset)
│   ├── taxonomy.py        sections / éléments / variantes / facettes
│   ├── oscmap.py          preset -> adresses OSC X-Air (ordre : gate en dernier)
│   ├── client.py          client UDP (push, grab, ping /info)
│   ├── storage.py         lecture/écriture JSON+YAML, validation par schéma
│   ├── xae_import.py      import/export .chn/.scn X-Air Edit
│   └── cli.py             interface en ligne de commande
│                          (show / validate / push / grab / import / export)
├── presets/               la bibliothèque, en YAML lisible et versionnable
├── docs/                  cette documentation
└── tests/
```

La GUI catalogue (Tauri, PyQt ou Gtk — à choisir) s'appuiera uniquement sur le
noyau : c'est le même objet `Preset` que lit le CLI et que pousse le client OSC.

## Règles d'architecture arrêtées en conception

### Blocs de preset et filtrage

`BLOCKS = config, hpf, eq, comp, gate` — chaque bloc est optionnel dans le
fichier ; sa présence = sa candidature à l'envoi. `Preset.keep_blocks()`
réalise le filtrage par cases-à-cocher de l'interface.

### Ordre d'envoi (sécurité live)

`PUSH_ORDER = config, hpf, eq, comp, gate` : le gate est **toujours** envoyé
en dernier ; un preset appliqué sur une tranche vocalise ne coupe pas la voix
avant que le reste soit en place. Le gain de compensation du compresseur
(`mgain`) vit dans le bloc comp mais pourra recevoir une case dédiée dans la GUI.

### Cartographie OSC vérifiée contre la scène de référence

Tirée des outils XAirGetScene/XAirSetScene (P. Maillot / K. Mitchell) et de
la scène `.scn` d'exemple authentique :

| Bloc | Nœud X-Air | Détails |
|---|---|---|
| Config | `{p}/config` | `{name, color, insrc, rtnsrc}` — pas d'icône en OSC ; insrc/rtnsrc jamais touchés |
| Preamp | `{p}/preamp` | `{trim, rtnsw, invert, hpon, hpf}` — le HPF vit ICI (hpon/hpf), pas sous `/hpf/` |
| Gate | `{p}/gate` | `{on, mode, thr, range, attack, hold, release, keysrc}` + sous-nœud `gate/filter` |
| Comp | `{p}/dyn` | `{on, mode, det, env, thr, ratio, knee, mgain, attack, hold, release, mix, keysrc, auto}` — ratio à crans fixes |
| EQ | `{p}/eq` + `eq/1..4` | bande = `{type, f, g, q}` ; types `LCut/LShv/PEQ/VEQ/HShv/HCut` |
| Headamp | `/headamp/NN` | nœud séparé = gain d'entrée — jamais touché |

(`{p}` = `/ch/NN` ou `/rtn/aux`.)

### Adresses interdites

Aucune adresse `/headamp`, `/preamp/trim` (gain préampli) ni `/mix/*`
(fader, mute) n'est jamais émise par `XAirClient.push`, qui refuse
explicitement ces préfixes. La capture ignore symétriquement le champ `trim`
du nœud preamp : c'est la garantie anti-larsen et anti-saut de niveau.

### Cas multi-canaux (variantes et paires)

Grosse caisse in/out, OverHead stéréo et chœurs multi-micros sont traités par
un **unique mécanisme de variante** : un attribut `variant` dans le preset,
et un éventuel drapeau « paire » qui ordonne l'application sur plusieurs
canaux canoniques (in → canal A, out → canal B). Pas de cas spécial dans le
moteur : la GUI parcourt la même structure.

### Quantisation console

La XR18 arrondit fréquences, Q et temps à sa grille interne : tout
comparateur (undo / comparer) doit tolérer des petits écarts (epsilon),
sinon des différences fantômes apparaissent après capture.

### Format filaire normalisé (certifié)

Sur OSC, la console transmet des valeurs normalisées 0..1 quantifiées.
Formules certifiées depuis Xscene2X.c (P. Maillot) et un dump réel
(XR18 fw 1.19), implémentées dans `codecs.py` :

| Paramètre | Formule (filaire -> réel) | Crans |
| --- | --- | --- |
| `preamp/hpf` | f = 20·e^(2.9957·x) (20–400 Hz) | 100 |
| `gate/thr` | −80 + 80·x dB (pas 0,5) | 160 |
| `gate/range` | 3 + 57·x dB (pas 1) | 57 |
| `gate, dyn/attack` | 120·x ms (pas 1) | 120 |
| `gate, dyn/hold` | 0,02·e^(11.5129·x) ms (0,02–2000) | 100 |
| `gate, dyn/release` | 5·e^(6.6846·x) ms (5–4000) | 100 |
| `dyn/thr` | −60 + 60·x dB (pas 0,5) | 120 |
| `dyn/ratio` | index **0-based** dans la liste des crans | 12 |
| `dyn/knee` | 5·x (pas 1) | 5 |
| `dyn/mgain` | 24·x dB (pas 0,5) | 48 |
| `dyn/mix` | 100·x % (`Xp_percent`) | — |
| `eq/f` | f = 20·1000^x Hz (20–20000, `Xp_frequency`) | 200 |
| `eq/g` | −15 + 30·x dB (pas 0,25) | 120 |
| `eq/q` | Q = 10·e^(−3.5066·x) (0,3–10) | 71 |
| `eq/N/type` | index 0-based dans LCut/LShv/PEQ/VEQ/HShv/HCut | 6 |

Au push, `codecs.encode_value` quantifie au cran le plus proche (même
comportement que la console) ; au grab, `decode_value` restitue la grandeur
réelle. La liste des ratios est 0-based (wire 7 = 5.0), confirmé par
`Xp_list` dans Xscene2X.c.

### Annuler / Comparer / Kit complet

- Chaque `push` (et chaque canal d'un `kit`) capture d'abord l'état courant
  du canal et l'écrit dans `~/.inspireair/snapshots/undo-chNN.yaml`
  (`--no-undo` pour désactiver, déconseillé en live). `undo` rejoue ce
  snapshot via le même chemin de push (mêmes garde-fous).
- `compare` compare ce que le preset enverrait à l'état capturé, **en
  valeurs filaires avec une tolérance d'un demi-cran** (`codecs.wire_epsilon`,
  base `WIRE_STEPS`) : en dessous, c'est de la quantisation console, pas un
  écart réel — pas de différences fantômes.
- `kit` : fichier YAML `kits/*.yaml` à clée `entries` (liste canal → preset,
  chemins relatifs au kit) ; undo par canal avant chaque push.

## Facettes vs arborescence

- **Arborescence** (sections et éléments) : ce que l'utilisateur parcourt.
- **Facettes** (variant, tessiture, style) : des filtres appliqués sur les
  presets ; stockés comme attributs, ajoutables sans toucher à la navigation.

## Limitations connues du squelette

- Les scènes `.scn` agrégées (plusieurs valeurs par nœud sur une ligne) ne
  sont pas encore parsées : l'import gère le format une-valeur-par-ligne.
- Adresses OSC à re-vérifier empiriquement contre le firmware de la console
  (protocole non officiel ; cartographie communautaire de référence).
- Le mode « Kit complet » (de nombreuses tranches en un envoi) attend
  l'interface : `push` s'applique à un canal à la fois pour l'instant.
