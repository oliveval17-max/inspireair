"""Traduction preset -> adresses OSC X-Air (cartographie communautaire, non officielle).

- Aucune adresse de headamp (/pre/trim) ni de mix fader (/mix/*) n'est jamais
  émise : sécurité anti-larsen et anti-saut de niveau.
- Le gate est toujours émis en dernier.
- Adresses à re-vérifier contre le firmware réel de la console (protocole
  non documenté officiellement) : voir docs/ARCHITECTURE.md.
"""

from __future__ import annotations

from typing import Optional, Union

from .model import PUSH_ORDER, EqBand, Preset

OscValue = Union[str, float, int]
OscItem = tuple[str, OscValue]

MAX_CHANNELS = 18

TOP_NODES = {"config": "config", "hpf": "hpf", "eq": "eq", "comp": "comp", "gate": "gate"}


def channel_prefix(channel: int) -> str:
    """Préfixe OSC d'un canal : 1-16 -> /ch/NN, 17-18 -> /rtn/aux."""
    if not 1 <= channel <= MAX_CHANNELS:
        raise ValueError(f"canal {channel} hors plage 1-{MAX_CHANNELS}")
    if channel <= 16:
        return f"/ch/{channel:02d}"
    return "/rtn/aux"


def preset_to_osc(preset: Preset, channel: int, blocks: Optional[set[str]] = None) -> list[OscItem]:
    """Construit la liste ordonnée (adresse, valeur) à envoyer à la console.

    L'ordre est celui de PUSH_ORDER : le gate est toujours en dernier.
    """
    scoped = preset.keep_blocks(blocks).validated()
    prefix = channel_prefix(channel)
    items: list[OscItem] = []
    for block in PUSH_ORDER:
        obj = getattr(scoped, block)
        if block == "config" and obj is not None:
            if obj.name:
                items.append((f"{prefix}/config/name", obj.name))
            items.append((f"{prefix}/config/color", obj.color))
            items.append((f"{prefix}/config/icon", obj.icon))
        elif block == "hpf" and obj is not None:
            items.append((f"{prefix}/hpf/on", int(obj.on)))
            items.append((f"{prefix}/hpf/freq", obj.freq))
        elif block == "eq" and obj is not None:
            items.append((f"{prefix}/eq/on", 1))
            for band in sorted(obj, key=lambda b: b.band):
                base = f"{prefix}/eq/{band.band}"
                items.append((f"{base}/type", band.type))
                items.append((f"{base}/freq", band.freq))
                items.append((f"{base}/g", band.gain))
                items.append((f"{base}/q", band.q))
        elif block == "comp" and obj is not None:
            items.append((f"{prefix}/comp/on", int(obj.on)))
            items.append((f"{prefix}/comp/thr", obj.thr))
            items.append((f"{prefix}/comp/ratio", obj.ratio))
            items.append((f"{prefix}/comp/att", obj.attack))
            items.append((f"{prefix}/comp/rel", obj.release))
            items.append((f"{prefix}/comp/knee", obj.knee))
            items.append((f"{prefix}/comp/mgain", obj.mgain))
            items.append((f"{prefix}/comp/wdm", obj.wdm))
        elif block == "gate" and obj is not None:
            items.append((f"{prefix}/gate/on", int(obj.on)))
            items.append((f"{prefix}/gate/thr", obj.thr))
            items.append((f"{prefix}/gate/rng", obj.range))
            items.append((f"{prefix}/gate/att", obj.attack))
            items.append((f"{prefix}/gate/hold", obj.hold))
            items.append((f"{prefix}/gate/rel", obj.release))
    return items


def capture_queries(channel: int) -> list[str]:
    """Adresses à interroger pour « Aspirer la tranche » (dans l'ordre PUSH_ORDER)."""
    prefix = channel_prefix(channel)
    queries: list[str] = [
        f"{prefix}/config/name",
        f"{prefix}/config/color",
        f"{prefix}/config/icon",
        f"{prefix}/hpf/on",
        f"{prefix}/hpf/freq",
        f"{prefix}/gate/on",
        f"{prefix}/gate/thr",
        f"{prefix}/gate/rng",
        f"{prefix}/gate/att",
        f"{prefix}/gate/hold",
        f"{prefix}/gate/rel",
        f"{prefix}/comp/on",
        f"{prefix}/comp/thr",
        f"{prefix}/comp/ratio",
        f"{prefix}/comp/att",
        f"{prefix}/comp/rel",
        f"{prefix}/comp/knee",
        f"{prefix}/comp/mgain",
        f"{prefix}/comp/wdm",
    ]
    for band in range(1, 5):
        queries.extend(
            [
                f"{prefix}/eq/{band}/type",
                f"{prefix}/eq/{band}/freq",
                f"{prefix}/eq/{band}/g",
                f"{prefix}/eq/{band}/q",
            ]
        )
    queries.append(f"{prefix}/eq/on")
    return queries
