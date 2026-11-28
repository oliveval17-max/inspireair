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
2. **Interface graphique** — voir la section « GUI : décisions actées » ci-dessous.
3. **Diffusion** — installation propre (pipx / .deb), distribution communautaire
   des presets.

---

## GUI : décisions actées (novembre 2026)

Décisions prises avec l'utilisateur, point par point, avant toute ligne de code
de GUI.

### Cibles d'usage

- **Laptop uniquement** — pas de smartphone/tablette : réflexes clavier/souris,
  risque de fausses manip en live sur écran tactile. InspireAir est un poste de
  travail de préparation et d'assistance ; le mix de secours reste sur l'app
  mobile Behringer.
- Le **CLI reste le socle** : la GUI est une couche au-dessus des mêmes modules
  (`model`, `codecs`, `oscmap`, `snapshot`, `kit`), pas un moteur parallèle.

### Framework

- **PySide6** (portage officiel Qt pour Python, licence **LGPL**) — compatible
  avec la licence MIT du projet et la distribution communautaire visée.
  PyQt6 écarté (GPL/commercial : plafonnerait la diffusion).

### Principes visuels

- Thème sombre, présentation moderne, sections nettement cloisonnées.
- **Aucune icône ni emoji pour les instruments** : libellés typographiés, un
  filet de couleur discret par section (écho sage des couleurs de tranche XR18).
  Objectif : un rendu « pro » même aux yeux des novices.
- Logo SVG en filigrane de la fenêtre principale (opacité très faible, ≤ 8 %,
  optionnel) — à dessiner en SVG dans le dépôt.
- **Icône d'application à concevoir** (idée notée, sans urgence).

### Structure de la fenêtre principale

- **Une seule fenêtre, vues empilées + fil d'Ariane** (Accueil > Batterie >
  Grosse caisse > Rock punchy). Dialogues séparés réservés aux tâches cadrées :
  Aspirer, Importer, Comparer.
- **Navigation taxonomie en panneau latéral + cartes** : sections à gauche
  (6 sections), éléments au centre, presets en cartes cliquables (notes de prise
  de son, mini-courbe EQ, badges HPF/Gate/EQ/Dyn). Trois clics maximum, position
  toujours visible. Menus déroulants en cascade écartés.
- **Barre d'actions permanente** : les deux seuls « gros boutons » de
  l'application sont **Pousser** (avec sélecteur de canal cible) et **Annuler**
  (undo), raccourcis clavier dédiés. Ce sont les seuls gestes physiques, seuls
  dignes de boutons pleine largeur. « Comparer » en action secondaire.
- **Carte « Ma salle »** (future jauge d'environnement acoustique) sur la
  fenêtre d'accueil, au-dessus de la navigation : statut du profil de salle
  actif/inactif. Présente dès la conception, fonctionnelle au stade S1 de la
  jauge (voir section dédiée).
- **Barre d'état permanente** : type de console, adresse IP, état de connexion
  (voyant vert/rouge), version d'InspireAir, mode Novice/Pro.
- **Encart crédits** : pied de fenêtre + boîte « À propos » —
  « Conception oliveval17-max avec Mistral — d'après le travail de
  P. Maillot (X32-Behringer) et K. Mitchell ».

### Modes Novice / Pro

- Même moteur, deux habillages : un interrupteur, pas deux logiciels.
- **Novice** : guidé et assisté, phrases rédigées explicatives, choix restreints,
  valeurs avancées masquées.
- **Pro** : mêmes données en panneau dense, valeurs éditables, dry-run et
  filtrage de blocs accessibles directement.

---

## Internationalisation (fr / en / de)

> Question de l'utilisateur (novembre 2026) : le logiciel fini pourra-t-il
> exister en anglais et en allemand ? Oui — mais **un seul logiciel, trois
> langues**, pas trois versions séparées.

### Approche retenue

- La traduction vit dans des **fichiers de langue**, pas dans le code :

  ```
  resources/i18n/
    inspireair_fr.ts   ← français (langue d'origine)
    inspireair_en.ts   ← anglais
    inspireair_de.ts   ← allemand
  ```

- Langue choisie au lancement (détection du système + menu de préférences).
- **PySide6 embarque l'outillage** (Qt Linguist, fichiers `.ts`/`.qm`) : un des
  bénéfices secondaires du choix du framework. Ajouter une 4e langue plus tard
  = traduire un fichier de plus, zéro code.
- Traductions rédigées avec attention au **vocabulaire métier authentique**
  (ex. allemand : *Klangregelung*, *Rauschsperre*) plutôt qu'au mot-à-mot.

### Les trois subtilités à prévoir dès le début de la GUI

1. **Étiquettes de taxonomie** : ce sont des données, pas des textes d'interface.
   Prévoir un identifiant neutre par entrée (`kick-drum`, `snare-drum`…) et une
   étiquette par langue. À intégrer au modèle **dès le début**, sinon rétrofit
   pénible.
2. **Notes de prise de son des presets** : trois options — laisser en français,
   traduire à la main les standards (vitrine du projet), ou champ `notes` par
   langue. Penchant : traduire manuellement les standards.
3. **Discipline de code** : règle d'or « jamais de texte en dur dans la GUI » —
   tout passe par les fichiers de langue. À appliquer dès la première fenêtre.

### Calendrier

- Rien à faire aujourd'hui (cœur d'abord). La règle de discipline et les
  identifiants neutres de taxonomie entrent en jeu **dès le démarrage de la
  GUI** ; les fichiers `en`/`de` se traduiront quand l'interface sera stable.

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

## Support et remontée de bugs

> Question de l'utilisateur (novembre 2026) : comment un utilisateur signale un
> bug ? Deux portes, une même boîte — les geeks passent par GitHub, les novices
> par un mail.

### Dispositif à deux portes

- **Porte geek** → **Issues GitHub**, avec templates d'issue à prévoir
  (champs guidés) : « bug » et « suggestion de preset » — pour éviter les
  issues vagues.
- **Porte novice** → adresse **Proton Mail** (confidentiel, crédible, cohérent
  avec l'esprit community du projet) ; à créer par l'utilisateur
  (ex. `inspireair@proton.me`). Lien cliquable dans la fenêtre **« À propos »**
  de la GUI, avec la checklist ci-dessous **affichée directement dans la
  fenêtre** (pas dans un fichier à chercher). L'adresse sera aussi ajoutée au
  README dès sa création.

### Checklist « rapport utile dès le premier mail »

À afficher dans « À propos » :

1. Ce qu'on a fait / ce qu'on attendait / ce qui s'est passé (trois phrases).
2. Version d'InspireAir + modèle/firmware de console — **déjà affichés dans la
   barre d'état**, l'utilisateur n'a qu'à les recopier.
3. Le fichier preset en cause, s'il y en a un.
4. Une capture d'écran si le problème est visuel.
5. Facultatif : le snapshot undo (`~/.inspireair/snapshots/`), très
   diagnostique.

### Cerise future : `inspireair report`

Commande CLI + bouton GUI qui **collecte automatiquement** (version, `/info`
de la console, fichier preset) et affiche un texte prêt à copier-coller dans le
mail. Zéro effort pour le novice, rapport parfait pour nous.

### Règle de courtoisie / confidentialité

Ne jamais demander les snapshots contenant le mix d'un tiers sans l'accord de
l'utilisateur ; l'adresse IP locale de la console n'est pas une donnée sensible.

---

## Retours de la communauté (premier post FB, novembre 2026)

Première présentation d'InspireAir sur un groupe Facebook français Behringer XR.
Retours positifs ; demandes concrètes à traiter comme backlog de presets :

- **Voix** : féminine (micro Sennheiser), masculine (Sennheiser e835) —
  demande explicite de Twipsi K.
- **Guitares** : acoustique en DI, électrique (SM58) — demande explicite ;
  une remarque nuancée d'un autre utilisateur (« moins utile pour la guitare
  électrique ») confirme que la valeur perçue porte sur les instruments
  **à traitement** (kick, snare, OH, chant, sax, trompette).
- **Cuivres** : sax, trompette — cités spontanément comme prioritaires.

Enseignements :

- La demande du monde réel correspond à la taxonomie existante — pas de
  refonte à prévoir, l'arborescence est validée de l'extérieur.
- Les demandes arrivent avec des micros précis (e835, SM58) : le format
  « preset documenté avec micros conseillés » répond exactement à l'attente.
- Un utilisateur du groupe envisage de passer à Linux grâce au projet —
  candidat potentiel au rôle de bêta-testeur Windows le moment venu (la
  compilation Windows sera testée par un volontaire, pas livrée à l'aveugle).

---

## Autres idées en réserve

- Suffixage automatique des paires dans le moteur de kit (« OH G » / « OH D »).
- Variantes grosse caisse Batte / Résonance ; caisse claire Top+Bottom.
- Styles par diff : dériver « Funk sec », « Jazz ouvert » du socle Rock punchy.
- Capture « Aspirer la tranche » en un clic dans la GUI.
