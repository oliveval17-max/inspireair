"""Import / export des fichiers texte X-Air Edit (.chn, .scn, .chp).

Deux formes de lignes coexistent (format vérifié sur un export réel
X-Air Edit, tranche HiHat) :

- forme « strip » (export de tranche) : nœuds agrégés, sans préfixe de canal :

    /preamp +0.0 OFF OFF ON 248
    /gate ON GATE -74.5 60.0 5 50.2 504 SELF
    /eq/3 PEQ 4k52 +14.5 2.0

- forme « scène » : mêmes nœuds agrégés, préfixés par canal (/ch/NN/...).

Les fréquences utilisent la notation k de la console (Xr_float du code de
référence) : « 4k52 » = 4520 Hz, « 9k35 » = 9350 Hz.

Sécurités : /mix (fader, mute), /preamp/trim, /gate/filter et /dyn/filter
(side-chain), keysrc et modes ne sont jamais importés ; à l'export, la ligne
/preamp (qui porte le HPF mais aussi le trim) est volontairement omise pour
ne jamais écraser le gain d'entrée lors d'un rappel dans X-Air Edit.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import asdict, replace
from typing import Any, Optional

from .model import Comp, Gate, Hpf, Preset

CHANNEL_RE = re.compile(r"^/(ch|bus|rtn/aux)/(\d{1,2})(/.*)?$")
EQ_TYPES = {"PEQ", "VEQ4", "VEQ6", "HShv", "LShv", "LPF1", "HPF1"}
_EQ_TYPES_UPPER = {t.upper(): t for t in EQ_TYPES}
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


def parse_chn(text: str) -> list[tuple[str, list[str]]]:
    """Extrait les lignes OSC (adresse, arguments) d'un fichier .chn/.scn."""
    entries: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("/"):
            continue
        try:
            parts = shlex.split(line)
        except ValueError:
            parts = line.split()
        if parts:
            entries.append((parts[0], parts[1:]))
    return entries


def _xr_float(raw: str) -> float:
    """Décodage numérique console : « 4k52 » -> 4520, « +15.0 » -> 15.0."""
    raw = raw.strip().lstrip("+")
    lower = raw.lower()
    if "k" in lower:
        i = lower.index("k")
        ival = int(raw[:i]) if raw[:i] else 0
        dec = raw[i + 1 :]
        value = ival * 1000.0
        if dec:
            value += int(dec) * 10 ** (len(dec) - 1)
        return value
    return float(raw)


def _to_bool(raw: str) -> bool:
    return raw.strip().strip('"').upper() in ("ON", "1", "YES", "TRUE")


def _is_number(raw: str) -> bool:
    try:
        float(raw.strip().lstrip("+"))
        return True
    except ValueError:
        return False


def _channel_of(address: str, channel: int) -> Optional[str]:
    match = CHANNEL_RE.match(address)
    if not match:
        return None
    kind, number, rest = match.group(1), int(match.group(2)), match.group(3) or ""
    if kind == "ch" and number != channel:
        return None
    return rest


def chn_to_preset_values(text: str, channel: int) -> dict[str, Any]:
    """Convertit un contenu .chn/.scn en dictionnaire de preset (canal unique).

    Accepte la forme strip (nœuds sans préfixe de canal), la forme scène
    (/ch/NN/nœud agrégé) et la forme feuille (/ch/NN/nœud/param valeur).
    """
    values: dict[str, Any] = {}
    for address, args in parse_chn(text):
        rest = _channel_of(address, channel)
        if rest is not None:
            parts = rest.strip("/").split("/")
            if len(parts) == 1:
                _ingest_node(values, parts[0], args)
            else:
                _ingest(values, parts, args[0] if args else "")
            continue
        parts = address.strip("/").split("/")
        if parts[0] in ("mix", "headamp"):
            continue
        if len(parts) == 2 and parts[0] == "eq" and parts[1].isdigit() and len(args) >= 4:
            _ingest_node(values, parts, args)
        elif len(parts) == 1:
            _ingest_node(values, parts[0], args)
        elif args:
            _ingest(values, parts, args[0])
    return values


def _ingest_node(values: dict[str, Any], node: Any, args: list[str]) -> None:
    """Décode un nœud agrégé positionnel (formes strip et scène)."""
    if not args:
        return
    if isinstance(node, list):
        parts = node
        if parts[0] == "eq" and len(parts) == 2 and parts[1].isdigit() and len(args) >= 4:
            _ingest_eq_band(values, int(parts[1]), args)
        return
    if node == "preamp" and len(args) >= 5:
        hpf = values.setdefault("hpf", {})
        hpf["on"] = _to_bool(args[3])
        try:
            hpf["freq"] = _xr_float(args[4])
        except ValueError:
            pass
    elif node == "gate" and len(args) >= 7:
        gate = values.setdefault("gate", {})
        gate["on"] = _to_bool(args[0])
        try:
            gate.update(
                {
                    "thr": _xr_float(args[2]),
                    "range": _xr_float(args[3]),
                    "attack": _xr_float(args[4]),
                    "hold": _xr_float(args[5]),
                    "release": _xr_float(args[6]),
                }
            )
        except ValueError:
            pass
    elif node == "dyn" and len(args) >= 12:
        comp = values.setdefault("comp", {})
        comp["on"] = _to_bool(args[0])
        try:
            comp.update(
                {
                    "thr": _xr_float(args[4]),
                    "ratio": _xr_float(args[5]),
                    "knee": _xr_float(args[6]),
                    "mgain": _xr_float(args[7]),
                    "attack": _xr_float(args[8]),
                    "hold": _xr_float(args[9]),
                    "release": _xr_float(args[10]),
                    "mix": _xr_float(args[11]),
                }
            )
        except ValueError:
            pass
    elif node == "config":
        config = values.setdefault("config", {})
        if not _is_number(args[0]):
            config["name"] = args[0].strip('"')
        if len(args) >= 2 and _is_number(args[1]):
            config["color"] = int(float(args[1]))


def _ingest_eq_band(values: dict[str, Any], band_no: int, args: list[str]) -> None:
    eq_bands: list[dict[str, Any]] = values.setdefault("eq", [])
    band = next((b for b in eq_bands if b["band"] == band_no), None)
    if band is None:
        band = {"band": band_no}
        eq_bands.append(band)
    try:
        canonical = _EQ_TYPES_UPPER.get(str(args[0]).upper())
        if canonical:
            band["type"] = canonical
        band["freq"] = _xr_float(args[1])
        band["gain"] = _xr_float(args[2])
        band["q"] = _xr_float(args[3])
    except (ValueError, IndexError):
        pass


def _ingest(values: dict[str, Any], parts: list[str], raw: str) -> None:
    """Forme feuille : /ch/NN/nœud/param valeur (une valeur par ligne)."""
    if not raw:
        return
    try:
        if parts[0] == "config" and len(parts) == 2:
            config = values.setdefault("config", {"name": "", "color": 0})
            if parts[1] == "name":
                config["name"] = raw.strip('"')
            elif parts[1] == "color":
                config["color"] = int(raw)
        elif parts[0] in ("hpf", "preamp") and len(parts) == 2:
            hpf = values.setdefault("hpf", {"on": False, "freq": 100.0})
            if parts[1] in ("on", "hpon"):
                hpf["on"] = _to_bool(raw)
            elif parts[1] in ("freq", "hpf"):
                hpf["freq"] = _xr_float(raw)
        elif parts[0] == "gate" and len(parts) == 2:
            gate = values.setdefault("gate", {})
            if parts[1] == "on":
                gate["on"] = _to_bool(raw)
            elif parts[1] in GATE_MAP:
                gate[GATE_MAP[parts[1]]] = _xr_float(raw)
        elif parts[0] in ("comp", "dyn") and len(parts) == 2:
            comp = values.setdefault("comp", {})
            if parts[1] == "on":
                comp["on"] = _to_bool(raw)
            elif parts[1] in COMP_MAP:
                comp[COMP_MAP[parts[1]]] = _xr_float(raw)
        elif parts[0] == "eq" and len(parts) == 3:
            band_no = int(parts[1])
            eq_bands: list[dict[str, Any]] = values.setdefault("eq", [])
            band = next((b for b in eq_bands if b["band"] == band_no), None)
            if band is None:
                band = {"band": band_no}
                eq_bands.append(band)
            if parts[2] == "type" and raw in EQ_TYPES:
                band["type"] = raw
            elif parts[2] in ("freq", "f"):
                band["freq"] = _xr_float(raw)
            elif parts[2] == "q":
                band["q"] = _xr_float(raw)
            elif parts[2] == "g":
                band["gain"] = _xr_float(raw)
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


def _num(value: float) -> str:
    return f"{value:g}"


def preset_to_chn_lines(preset: Preset, channel: int) -> list[str]:
    """Exporte un preset au format strip X-Air Edit.

    La ligne /preamp (HPF + trim) est omise : elle porterait le gain
    d'entrée, qu'InspireAir ne touche jamais. Le HPF doit être vérifié
    dans X-Air Edit après rappel.
    """
    lines = [
        "# Export InspireAir — format strip X-Air Edit",
        "# Sécurité : trim préampli et fader jamais exportés (ligne /preamp omise).",
        "# Vérifie le HPF et le gain après rappel dans X-Air Edit.",
    ]
    if preset.config:
        if preset.config.name:
            lines.append(f'/config/name "{preset.config.name}"')
        lines.append(f"/config/color {preset.config.color}")
    if preset.gate:
        gate = preset.gate
        lines.append(
            f"/gate {_num(float(gate.on))} GATE {_num(gate.thr)} {_num(gate.range)}"
            f" {_num(gate.attack)} {_num(gate.hold)} {_num(gate.release)} SELF"
        )
    if preset.comp:
        comp = preset.comp
        lines.append(
            f"/dyn {_num(float(comp.on))} COMP PEAK LOG {_num(comp.thr)} {_num(comp.ratio)}"
            f" {_num(comp.knee)} {_num(comp.mgain)} {_num(comp.attack)} {_num(comp.hold)}"
            f" {_num(comp.release)} {_num(comp.mix)} SELF OFF"
        )
    if preset.eq:
        lines.append("/eq ON")
        for band in sorted(preset.eq, key=lambda b: b.band):
            lines.append(f"/eq/{band.band} {band.type} {_num(band.freq)} {_num(band.gain)} {_num(band.q)}")
    return lines


def rename_element(preset: Preset, element: str, instrument: Optional[str] = None) -> Preset:
    return replace(preset, element=element, instrument=instrument or preset.instrument)
