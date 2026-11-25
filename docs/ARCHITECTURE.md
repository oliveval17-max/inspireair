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
