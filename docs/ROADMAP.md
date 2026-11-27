# Feuille de route InspireAir

Ce document consigne les orientations longues et les idées validées, pour ne rien
perdre et garder le cœur du projet focalisé. L'ordre des priorités est discuté
avec l'utilisateur ; rien ici n'engage de date.

---

## Priorités actuelles (cœur du projet)

1. **Bibliothèque de standards** — validation à l'oreille du kit batterie
   « Rock punchy », déclinaison d'autres styles par diff (Funk sec, Jazz ouvert),
   ouverture des autres sections (Basse, Voix, Guitares, Claviers, Cuivres & Vents,
   Percussions).
2. **Interface graphique** — mode Novice/Pro, navigation Instrument → Élément →
   Style, recherche/favoris, mini-courbes EQ. Choix du framework à instruire
   (Tauri / PyQt / GTK).
3. **Diffusion** — installation propre (pipx / .deb), distribution communautaire
   des presets.

---

## Idée archivée : Jauge d'environnement acoustique (profil de salle)

> Idée de l'utilisateur, novembre 2026, issue d'expériences de balance stressantes
> dans des salles acoustiquement dégradées (hangar en tôle, réfectoire béton) :
> réverbération, harmoniques désagréables, larsens.

### Principe

Évaluer les défauts acoustiques de la salle (modes de résonance, fréquences à
risque de larsen, zones de réverbération gênantes) à partir du son capté en
retour par les micros, puis :

- **informer** : proposer un spectre ou des plages de fréquences à « assourdir »
  dans le mix ou sur les canaux concernés ;
- **décliner** : garder les presets standards **purs** (dépôt) et proposer, via
  un bouton, le preset standard décliné selon les défauts acoustiques de la
  pièce — sans jamais écraser le standard.

### Physique du sujet

Le larsen est une boucle micro → console → ampli → enceinte → salle → micro dont
certaines fréquences reviennent amplifiées. Ces fréquences dépendent des modes de
résonance de la salle (denses et longs dans le béton / la tôle), du placement
micro/enceinte et du gain. Le clap des mains est une impulsion large bande : ce
qui « traîne » après lui est la signature acoustique de la pièce.

### Les trois stades envisagés

| Stade | Fonction | Prérequis | Coût |
|---|---|---|---|
| **S1 — Profil de salle manuel** | L'utilisateur repère les fréquences gênantes (clap + RTA de X-Air Edit, ou à l'oreille) et les saisit ; InspireAir mémorise un « profil de salle » nommé et propose les déclinaisons de presets. | Aucun | Faible |
| **S2 — Analyse USB (clap + sweep)** | Capture audio 18×18 USB de la XR18, FFT du clap (diagnostic large) ou d'un sweep logarihmique émis par les enceintes (mesure fine), détection des résonances, rapport « fréquences à surveiller » par canal. | Capture ALSA + numpy, points de prise USB à certifier | Moyen |
| **S3 — Ring-out assisté** | Pendant la balance, surveillance des meters OSC : détection d'une tonalité sinusoïdale persistante (larsen naissant) → alerte + suggestion de notch immédiate. | Meters OSC, seuils robustes | Élevé |

### Architecture conceptuelle

```
Preset standard (dépôt)  ×  Profil de salle (~/.inspireair/rooms/)  →  Tranche déclinée
```

- Le profil de salle est une liste de consignes : `fréquence, atténuation
  suggérée, Q, portée (canal / bus / global)`, plus nom et notes.
- Le **fusion** preset × profil n'additionne pas bêtement les atténuations :
  si le preset atténue déjà −3 dB là où la salle demande −4, on propose une
  somme acoustique pondérée (~−6 dB), présentée à l'utilisateur **avant** push.
- Mode Novice : formulation pédagogique (« cette salle a tendance à hurler vers
  250 Hz… »). Mode Pro : notches détaillées, éditables.

### Limites assumées (règles produit)

1. **Mesurer la pièce, pas les presets** : procédure « mode mesure » — blocs
   (HPF/EQ/gate/comp) remis à neutre pendant l'analyse, puis restaurés
   (réutiliser l'infrastructure undo).
2. **Jauge ≠ garantie** : le larsen dépend aussi du volume, du placement des
   enceintes et des micros. Vocabulaire honnête dans l'UI : « fréquences à
   surveiller », « suggestion », jamais « larsen impossible ».
3. **Aucune modification du mix sans validation** : le profil **propose**,
   l'utilisateur **applique** (philosophie du projet).
4. **Les presets standards restent purs** : la déclinaison vit chez
   l'utilisateur, jamais dans le dépôt.

### Questions ouvertes

- [ ] Points de prise des envois USB de la XR18 (avant/après EQ ?) — à certifier
      sur la console avant S2.
- [ ] Format du profil de salle (YAML simple, inspiré des presets ?).
- [ ] Extension du modèle : les consignes de salle s'appliquent-elles aussi aux
      bus/matrix ou seulement aux tranches ?
- [ ] Sweep : généré par InspireAir (fichier WAV) ou réutilise-t-on une piste de
      référence ? (REW sur Linux existe ; on s'inspire, on ne dépend pas.)
- [ ] Résolution du clap seul : ~50 Hz pour 20 ms analysées — suffisant pour un
      diagnostic « indicateur large », insuffisant pour les graves ; garder le
      sweep comme option Pro.

---

## Autres idées en réserve

- Suffixage automatique des paires dans le moteur de kit (« OH G » / « OH D »).
- Variantes grosse caisse Batte / Résonance ; caisse claire Top+Bottom.
- Styles par diff : dériver « Funk sec », « Jazz ouvert » du socle Rock punchy.
- Capture « Aspirer la tranche » en un clic dans la GUI.
