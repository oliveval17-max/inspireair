"""Taxonomie InspireAir : sections, éléments, variantes et facettes.

Principes arrêtés en conception :
- l'arborescence porte l'usage (section -> element -> style) ;
- les variantes (kick batte/résonance) et la tessiture (voix Homme/Femme)
  sont des attributs du preset, pas des branches de menu ;
- les cas multi-canaux (kick in+out, OverHead stéréo, chœurs) utilisent
  le drapeau de paire.
"""

SECTIONS: dict[str, list[str]] = {
    "Batterie": [
        "Grosse caisse",
        "Caisse claire",
        "Tom alto 10",
        "Tom alto 12",
        "Tom médium 13",
        "Tom basse 14-16",
        "Overhead",
        "Charley",
    ],
    "Percussions": [
        "Djembés",
        "Bongos",
        "Congas",
        "Woodblock",
        "Chimes",
        "Shaker",
        "Tambourine",
        "Cabasa",
        "Cajón",
        "Cowbell",
    ],
    "Guitares": ["Basse", "Lead", "Rythmique", "Acoustique (piezo)", "Acoustique (micro)", "Banjo", "Ukulélé"],
    "Claviers": ["Piano acoustique", "Piano électrique", "Orgue", "Synthés"],
    "Cuivres & Vents": ["Trompette", "Trombone", "Saxophone", "Harmonica"],
    "Voix": ["Lead", "Backing", "Chœurs"],
}

VARIANTS: dict[str, list[str]] = {
    "Grosse caisse": ["Micro unique", "Batte", "Résonance"],
    "Caisse claire": ["Top", "Top+Bottom"],
    "Overhead": ["Mono", "Paire A-B"],
}

TESSITURES = ["Homme", "Femme"]

STYLES = [
    "Rock punchy",
    "Funk sec",
    "Jazz ouvert",
    "Disco mat",
    "Acoustique naturel",
    "Pop moderne",
    "Métal",
    "Blues",
    "Néo-soul",
]

PAIR_ELEMENTS = {"Overhead", "Chœurs"}
