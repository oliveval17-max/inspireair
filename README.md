# InspireAir

> *Inspirez vos mixes. Expirez vos tranches.*
> *Aspirez le son de vos meilleures balances.*

Bibliothèque de presets de tranches de console pour les mixeurs **Behringer X-Air** (XR18, XR16, XR12, X18, MR18), pilotés depuis **Linux** en OSC (UDP 10024). Conçue à la fois pour les **novices de l'ingénierie son** (presets standards pédagogiques, explications en langage humain) et pour les **pros** qui veulent capitaliser leurs balances.

## Fonctionnement

L'utilisateur choisit un canal cible (ex. CH 02), navigue dans le catalogue
**Instrument → Élément → Style**, coche éventuellement les blocs à appliquer
(HPF, Gate, EQ, Compressor, Config), et pousse le preset vers la console —
le résultat est visible en direct dans X-Air Edit.

### Sécurités intégrées

- Le **gain préampli** (headamp trim) et le **fader** ne sont jamais modifiés :
  pas de larsen, pas de saut de niveau en live.
- Le **gate est toujours envoyé en dernier** (jamais de voix coupée par un
  preset mal ciblé).
- Le **gain de compensation du compresseur** (`mgain`) a sa propre case,
  indépendante du compresseur.
- Le bloc **Config** (nom, couleur, icône de tranche) est opt-in, séparé du son.

## Installation

```bash
pip install .
inspireair --help
```

## Usage CLI

```bash
inspireair show presets/batterie/grosse-caisse-micro-unique/funk-sec.yaml
inspireair validate presets/voix/lead-femme-rock-punchy.yaml
inspireair push presets/batterie/caisse-claire-top-rock-punchy.yaml \
    --host 192.168.1.100 --channel 2 --blocks hpf,eq,comp,gate
inspireair grab --host 192.168.1.100 --channel 2 -o ma-balance.yaml
inspireair import scene.xchn -o scene-importee.yaml
```

- `push` : applique un preset sur un canal (ordre d'envoi garanti :
  Config → HPF → EQ → Comp → Gate, avec `--dry-run` pour prévisualiser).
- `grab` : la fonction « Aspirer la tranche » — lit les paramètres OSC du canal
  et les sauvegarde dans la bibliothèque.
- `import` : convertit un fichier `.chn` / `.scn` de X-Air Edit en preset.

## Modèle de données

Chaque preset est un fichier JSON ou YAML lisible et versionnable :

```json
{
  "instrument": "Batterie",
  "element": "Caisse claire",
  "variant": "Top",
  "style": "Rock punchy",
  "notes": "SM57 à 3 cm du bord, peau sablée.",
  "hpf": { "on": true, "freq": 100 },
  "gate": { "on": true, "thr": -28.0, "range": 18.0, "attack": 1, "hold": 15, "release": 120 },
  "eq": [
    { "band": 1, "type": "PEQ", "freq": 200, "gain": 3.5, "q": 2.0 }
  ],
  "comp": { "on": true, "thr": -16.0, "ratio": 4.0, "attack": 12, "release": 90, "mgain": 3.0 }
}
```

La taxonomie complète et les règles de modélisation (variantes, facettes) sont
décrites dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Le schéma de
validation se trouve dans
[src/inspireair/schema/inspireair-preset.schema.json](src/inspireair/schema/inspireair-preset.schema.json).

## Taxonomie

6 sections : **Batterie, Percussions, Guitares, Claviers, Cuivres & Vents, Voix**.
- Usage en arborescence (ex. Voix : Lead / Backing / Chœurs), **variantes**
  (kick micro unique / batte / résonance) et **tessiture** (Homme / Femme)
  en attributs, pas en branches de menu.
- L'envoi multi-canaux (kick in+out, paire d'OverHead, chœurs) est couvert par
  un unique mécanisme de paire/variante.

## Développement

```bash
pip install -e .[dev]
pytest
```

## État du projet

Squelette initial : noyau OSC (push / capture), modèle de preset validé par
schéma, import `.chn`, CLI. La GUI catalogue est planifiée (voir
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).

⚠️ Le protocole OSC X-Air est non officiel : les adresses et plages de
paramètres sont issues de la cartographie communautaire et doivent être
vérifiées contre votre firmware (les presets d'exemple passent `--dry-run`).

## Licence

[MIT](LICENSE)
