"""Modèle de données des presets InspireAir.

Sans dépendance externe : importable partout, sérialisable en JSON/YAML.
Convention d'unités (celles attendues dans les fichiers de preset) :
- les fréquences sont en Hz, les gains en dB, les Q en facteur ;
- attaque, hold et relâchement (gate et comp) sont en millisecondes ;
- la console quantise ces valeurs sur sa grille interne : les comparaisons
  (undo/comparer) doivent donc tolérer de petits écarts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from typing import Any, Optional

BLOCKS = ("config", "hpf", "eq", "comp", "gate")

PUSH_ORDER = ("config", "hpf", "eq", "comp", "gate")

# Types de bande EQ réels de la série X-Air (défaut X32 : VEQ4/VEQ6/LPF1/HPF1).
EQ_TYPES = ("LCut", "LShv", "PEQ", "VEQ", "HShv", "HCut")

EQ_TYPE_ALIASES = {"VEQ4": "VEQ", "VEQ6": "VEQ", "HPF1": "LCut", "LPF1": "HCut"}

# Le ratio du compresseur X-Air est une échelle à crans fixes, pas continue.
COMP_RATIOS = (1.1, 1.3, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0, 20.0, 100.0)

TESSITURES = ("Homme", "Femme")


class PresetError(ValueError):
    """Valeur hors plage ou structure de preset invalide."""


def _check(name: str, value: float, low: float, high: float) -> float:
    if not low <= value <= high:
        raise PresetError(f"{name} = {value} hors plage [{low}, {high}]")
    return value


@dataclass
class Hpf:
    on: bool = True
    freq: float = 100.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Hpf":
        return cls(on=bool(data.get("on", True)), freq=float(data.get("freq", 100.0)))

    def validated(self) -> "Hpf":
        _check("hpf.freq", self.freq, 20.0, 400.0)
        return self


@dataclass
class Gate:
    on: bool = True
    thr: float = -28.0
    range: float = 18.0
    attack: float = 1.0
    hold: float = 15.0
    release: float = 120.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Gate":
        return cls(
            on=bool(data.get("on", True)),
            thr=float(data.get("thr", -28.0)),
            range=float(data.get("range", 18.0)),
            attack=float(data.get("attack", 1.0)),
            hold=float(data.get("hold", 15.0)),
            release=float(data.get("release", 120.0)),
        )

    def validated(self) -> "Gate":
        _check("gate.thr", self.thr, -80.0, 0.0)
        _check("gate.range", self.range, 3.0, 60.0)
        _check("gate.attack", self.attack, 0.0, 120.0)
        _check("gate.hold", self.hold, 0.02, 2000.0)
        _check("gate.release", self.release, 5.0, 4000.0)
        return self


@dataclass
class EqBand:
    band: int = 1
    type: str = "PEQ"
    freq: float = 1000.0
    gain: float = 0.0
    q: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EqBand":
        return cls(
            band=int(data.get("band", 1)),
            type=str(data.get("type", "PEQ")),
            freq=float(data.get("freq", 1000.0)),
            gain=float(data.get("gain", 0.0)),
            q=float(data.get("q", 1.0)),
        )

    def validated(self) -> "EqBand":
        self.type = EQ_TYPE_ALIASES.get(self.type, self.type)
        if self.band not in (1, 2, 3, 4):
            raise PresetError(f"eq.band = {self.band} invalide (attendu 1 à 4)")
        if self.type not in EQ_TYPES:
            raise PresetError(f"eq.type = {self.type!r} invalide, attendu parmi {EQ_TYPES}")
        _check("eq.freq", self.freq, 20.0, 20000.0)
        _check("eq.gain", self.gain, -15.0, 15.0)
        _check("eq.q", self.q, 0.1, 10.0)
        return self


@dataclass
class Comp:
    on: bool = True
    thr: float = -16.0
    ratio: float = 4.0
    attack: float = 12.0
    release: float = 90.0
    knee: float = 2.0
    mgain: float = 3.0
    mix: float = 100.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Comp":
        return cls(
            on=bool(data.get("on", True)),
            thr=float(data.get("thr", -16.0)),
            ratio=float(data.get("ratio", 4.0)),
            attack=float(data.get("attack", 12.0)),
            release=float(data.get("release", 90.0)),
            knee=float(data.get("knee", 2.0)),
            mgain=float(data.get("mgain", 3.0)),
            mix=float(data.get("mix", data.get("wdm", 100.0))),
        )

    def validated(self) -> "Comp":
        _check("comp.thr", self.thr, -60.0, 0.0)
        if not any(abs(self.ratio - allowed) < 0.01 for allowed in COMP_RATIOS):
            raise PresetError(
                f"comp.ratio = {self.ratio} n'est pas un cran valide (crans : {COMP_RATIOS})"
            )
        _check("comp.attack", self.attack, 0.0, 120.0)
        _check("comp.release", self.release, 5.0, 4000.0)
        _check("comp.knee", self.knee, 0.0, 5.0)
        _check("comp.mgain", self.mgain, 0.0, 24.0)
        _check("comp.mix", self.mix, 0.0, 100.0)
        return self


@dataclass
class ChannelConfig:
    """Le nom et la couleur de tranche. Pas d'icône : la série X-Air n'en expose
    pas en scène/OSC (contrairement au X32). Ne touche jamais à la source (insrc)."""

    name: str = ""
    color: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelConfig":
        return cls(
            name=str(data.get("name", "")),
            color=int(data.get("color", 0)),
        )

    def validated(self) -> "ChannelConfig":
        if len(self.name) > 12:
            raise PresetError("config.name trop long (12 caractères maximum)")
        _check("config.color", self.color, 0, 15)
        return self


@dataclass
class Preset:
    instrument: str
    element: str
    style: str
    variant: Optional[str] = None
    tessiture: Optional[str] = None
    notes: Optional[str] = None
    author: Optional[str] = None
    version: str = "1"
    config: Optional[ChannelConfig] = None
    hpf: Optional[Hpf] = None
    gate: Optional[Gate] = None
    eq: Optional[list[EqBand]] = None
    comp: Optional[Comp] = None

    def blocks(self) -> set[str]:
        return {name for name in BLOCKS if getattr(self, name)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Preset":
        try:
            instrument = str(data["instrument"])
            element = str(data["element"])
            style = str(data["style"])
        except KeyError as exc:
            raise PresetError(f"champ obligatoire manquant : {exc.args[0]}") from None
        eq_data = data.get("eq")
        return cls(
            instrument=instrument,
            element=element,
            style=style,
            variant=data.get("variant"),
            tessiture=data.get("tessiture"),
            notes=data.get("notes"),
            author=data.get("author"),
            version=str(data.get("version", "1")),
            config=ChannelConfig.from_dict(data["config"]) if data.get("config") else None,
            hpf=Hpf.from_dict(data["hpf"]) if data.get("hpf") else None,
            gate=Gate.from_dict(data["gate"]) if data.get("gate") else None,
            eq=[EqBand.from_dict(b) for b in eq_data] if eq_data else None,
            comp=Comp.from_dict(data["comp"]) if data.get("comp") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def validated(self) -> "Preset":
        if self.tessiture is not None and self.tessiture not in TESSITURES:
            raise PresetError(f"tessiture = {self.tessiture!r} invalide, attendu parmi {TESSITURES}")
        for attr, obj_name in (("config", "config"), ("hpf", "hpf"), ("gate", "gate"), ("comp", "comp")):
            obj = getattr(self, attr)
            if obj is not None:
                obj.validated()
        if self.eq:
            self.eq = [b.validated() for b in self.eq]
        return self

    def keep_blocks(self, blocks: Optional[set[str]]) -> "Preset":
        """Renvoie une copie ne contenant que les blocs demandés (aucun = tout garder)."""
        if not blocks:
            return self
        unknown = blocks - set(BLOCKS)
        if unknown:
            raise PresetError(f"bloc(s) inconnu(s) : {', '.join(sorted(unknown))}")
        return replace(
            self,
            config=self.config if "config" in blocks else None,
            hpf=self.hpf if "hpf" in blocks else None,
            eq=list(self.eq) if self.eq and "eq" in blocks else None,
            comp=self.comp if "comp" in blocks else None,
            gate=self.gate if "gate" in blocks else None,
        )

    def describe(self) -> str:
        """Description en langage humain, pour le mode novice."""
        parts: list[str] = [f"Preset {self.element} — {self.style}."]
        if self.hpf is not None:
            effect = "éviter le larsen" if self.hpf.freq >= 80 else "nettoyer les basses"
            parts.append(f"Coupe les fréquences sous {self.hpf.freq:.0f} Hz pour {effect}.")
        if self.eq:
            boosts = [f"{b.freq:.0f} Hz (+{b.gain:.1f} dB)" for b in self.eq if b.gain > 0]
            cuts = [f"{b.freq:.0f} Hz ({b.gain:.1f} dB)" for b in self.eq if b.gain < 0]
            if boosts:
                parts.append(f"Met en avant : {'; '.join(boosts)}.")
            if cuts:
                parts.append(f"Réduit : {'; '.join(cuts)}.")
        if self.comp is not None:
            parts.append(
                f"Compresse les passages trop forts (seuil {self.comp.thr:.0f} dB, "
                f"ratio {self.comp.ratio:.0f}:1) et les équilibre"
                + (f" avec +{self.comp.mgain:.0f} dB de compensation" if self.comp.mgain > 0 else "")
                + "."
            )
        if self.gate is not None:
            if self.gate.on:
                parts.append(
                    f"Seuil du coupe-bruit à {self.gate.thr:.0f} dB pour éliminer les bruits parasites."
                )
            else:
                parts.append("Le coupe-bruit est présent mais désactivé.")
        if self.config is not None:
            parts.append(f"Renomme la tranche « {self.config.name} » et change sa couleur.")
        return " ".join(parts)
