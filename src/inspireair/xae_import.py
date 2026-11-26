"""Import / export des fichiers texte X-Air Edit (.chn, .scn, .chp).

Ces fichiers contiennent une requête OSC par ligne, du type :

    /ch/01/gate/thr -28.0
    /ch/01/eq/1/type PEQ

Format empirique, établi avec X-Air Edit sur XR18 : les fichiers de scène
(.scn) agrègent plusieurs valeurs par nœud sur une seule ligne, ce parseur
ne gère que la forme « une valeur par ligne » ; les scènes complètes qui
n'utilisent pas cette forme déclenchent une erreur explicite.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import asdict, replace
from typing import Any, Optional

from .model import Comp, Gate, Hpf, Preset

CHANNEL_RE = re.compile(r"^/(ch|bus|rtn/aux)/(\d{1,2})(/.*)?$")
GATE_MAP = {"thr": "thr", "rng": "range", "att": "attack", "hold": "hold", "rel": "release"}
COMP_MAP = {
    "thr": "thr",
    "ratio": "ratio",
    "att": "attack",
    "hold": "hold",
    "rel": "release",
    "knee": "knee",
    "mgain": "mgain",
    "mix": "mix",
    "wdm": "mix",
}
EQ_TYPES = {"PEQ", "VEQ4", "VEQ6", "HShv", "LShv", "LPF1", "HPF1"}


def parse_chn(text: str) -> list[tuple[str, list[str]]]:
    """Extrait les lignes OSC exploitables d'un fichier .chn/.scn."""
    entries: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("/"):
            continue
        try:
            parts = shlex.split(line)
        except ValueError:
            parts = line.split()
        if len(parts) == 1:
            entries.append((parts[0], []))
        elif len(parts) == 2:
            entries.append((parts[0], [parts[1]]))
        else:
            raise ValueError(
                f"ligne multi-valeurs non supportée (format scène agrégée) : {line!r}"
            )
    return entries


def _channel_of(address: str, channel: int) -> Optional[str]:
    match = CHANNEL_RE.match(address)
    if not match:
        return None
    kind, number, rest = match.group(1), int(match.group(2)), match.group(3) or ""
    if kind == "ch" and number != channel:
        return None
    return rest


def chn_to_preset_values(text: str, channel: int) -> dict[str, Any]:
    """Convertit un contenu .chn/.scn en dictionnaire de preset (canal unique)."""
    values: dict[str, Any] = {}
    for address, args in parse_chn(text):
        rest = _channel_of(address, channel)
        if not rest or not args:
            continue
        parts = rest.strip("/").split("/")
        _ingest(values, parts, args[0])
    return values


def _ingest(values: dict[str, Any], parts: list[str], raw: str) -> None:
    try:
        if parts[0] == "config" and len(parts) == 2:
            config = values.setdefault("config", {"name": "", "color": 0, "icon": 0})
            if parts[1] == "name":
                config["name"] = raw.strip('"')
            elif parts[1] in ("color", "icon"):
                config[parts[1]] = int(raw)
        elif parts[0] == "hpf" and len(parts) == 2:
            hpf = values.setdefault("hpf", {"on": False, "freq": 100.0})
            if parts[1] == "on":
                hpf["on"] = raw.upper() == "ON" or bool(int(raw))
            else:
                hpf["freq"] = float(raw)
        elif parts[0] == "gate" and len(parts) == 2:
            gate = values.setdefault("gate", {})
            if parts[1] == "on":
                gate["on"] = raw.upper() == "ON" or bool(int(raw))
            elif parts[1] in GATE_MAP:
                gate[GATE_MAP[parts[1]]] = float(raw)
        elif parts[0] == "comp" and len(parts) == 2:
            comp = values.setdefault("comp", {})
            if parts[1] == "on":
                comp["on"] = raw.upper() == "ON" or bool(int(raw))
            elif parts[1] in COMP_MAP:
                comp[COMP_MAP[parts[1]]] = float(raw)
        elif parts[0] == "eq" and len(parts) == 3:
            band_no = int(parts[1])
            eq_bands: list[dict[str, Any]] = values.setdefault("eq", [])
            band = next((b for b in eq_bands if b["band"] == band_no), None)
            if band is None:
                band = {"band": band_no}
                eq_bands.append(band)
            if parts[2] == "type" and raw in EQ_TYPES:
                band["type"] = raw
            elif parts[2] in ("freq", "q"):
                band[parts[2]] = float(raw)
            elif parts[2] == "g":
                band["gain"] = float(raw)
    except ValueError:
        return


def _fill_defaults(values: dict[str, Any]) -> dict[str, Any]:
    if "gate" in values:
        values["gate"] = {k: v for k, v in asdict(Gate.from_dict(values["gate"])).items() if v is not None}
    if "comp" in values:
        values["comp"] = {k: v for k, v in asdict(Comp.from_dict(values["comp"])).items()}
    if "hpf" in values:
        values["hpf"] = {k: v for k, v in asdict(Hpf.from_dict(values["hpf"])).items()}
    return values


def preset_tag_from_rules(kind: str = "import") -> str:
    return "import X-Air Edit" if kind == "import" else kind


def finalize_preset(values: dict[str, Any], element_guess: str = "Importé") -> Preset:
    """Complète les champs d'usage puis construit le Preset."""
    values = _fill_defaults(values)
    if values.get("eq"):
        values["eq"] = [b for b in values["eq"] if "type" in b and "freq" in b]
    return Preset.from_dict(
        {
            "instrument": "Import",
            "element": values.pop("element", element_guess),
            "style": values.pop("style", "Non classé"),
            **values,
        }
    ).validated()


def preset_to_chn_lines(preset: Preset, channel: int) -> list[str]:
    """Exporte un preset en lignes OSC compatibles .chn."""
    from .oscmap import preset_to_osc

    return [f"{address} {value}" for address, value in preset_to_osc(preset, channel)]


def rename_element(preset: Preset, element: str, instrument: Optional[str] = None) -> Preset:
    return replace(preset, element=element, instrument=instrument or preset.instrument)
