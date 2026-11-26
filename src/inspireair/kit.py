"""Kit complet : appliquer une cohérence globale sur plusieurs tranches.

Un fichier kit liste des entrées canal -> preset ; chaque canal est
sauvegardé (undo) juste avant son push, chaque élément reste modifiable
séparément. Chemins de presets relatifs au fichier kit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .model import Preset
from .storage import load_preset


def load_kit(path: Path) -> list[tuple[int, Preset]]:
    data: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list) or not data["entries"]:
        raise ValueError(f"kit illisible (clée 'entries' attendue, non vide) : {path}")
    base = Path(path).parent
    plan: list[tuple[int, Preset]] = []
    for entry in data["entries"]:
        channel = int(entry["channel"])
        if not 1 <= channel <= 18:
            raise ValueError(f"canal {channel} hors plage 1-18 dans {path}")
        preset = load_preset(base / str(entry["preset"]))
        plan.append((channel, preset))
    return plan
