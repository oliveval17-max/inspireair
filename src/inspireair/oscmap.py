"""Traduction preset -> adresses OSC X-Air (cartographie communautaire, non officielle).

Constats établis par les outils de référence XAirGetScene/XAirSetScene
(P. Maillot / K. Mitchell) et une scène .scn authentique :
- le nœud du compresseur d'une tranche s'appelle **/dyn** et non /comp ;
- les feuilles EQ d'une bande sont /type, /f, /g, /q ;
- le HPF se trouve dans le nœud **preamp** (/ch/NN/preamp/hpon, /preamp/hpf) ;
- le gain d'entrée vit dans le nœud séparé **/headamp/NN**, jamais touché ;
- la configuration est {name, color, insrc, rtnsrc} : pas d'icône en OSC, et
  la source (insrc/rtnsrc) n'est jamais modifiée ;
- le mode du gate + sa clé (keysrc) ne sont pas écrasés par nos presets :
  on ne pousse que ce que le preset porte.

Garde-fous conservés : aucune adresse /headamp, /preamp/trim, /mix n'est émise,
et le gate est toujours le dernier bloc envoyé.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from .model import PUSH_ORDER, EqBand, Preset

OscValue = Union[str, float, int]
OscItem = tuple[str, OscValue]

MAX_CHANNELS = 18

# Champ X-Air présents dans la captation de nœud, utilisés pour décoder les réponses.
NODE_FIELDS: dict[str, list[str]] = {
    "config": ["name", "color", "insrc", "rtnsrc"],
    "preamp": ["trim", "rtnsw", "invert", "hpon", "hpf"],
    "gate": ["on", "mode", "thr", "range", "attack", "hold", "release", "keysrc"],
    "dyn": ["on", "mode", "det", "env", "thr", "ratio", "knee", "mgain", "attack", "hold", "release", "mix", "keysrc", "auto"],
    "eq": ["on"],
    "eq/{band}": ["type", "f", "g", "q"],
}


def channel_prefix(channel: int) -> str:
    """Préfixe OSC d'une tranche : 1-16 -> /ch/NN, 17-18 -> /rtn/aux."""
    if not 1 <= channel <= MAX_CHANNELS:
        raise ValueError(f"canal {channel} hors plage 1-{MAX_CHANNELS}")
    if channel <= 16:
        return f"/ch/{channel:02d}"
    return "/rtn/aux"


def preset_to_osc(preset: Preset, channel: int, blocks: Optional[set[str]] = None) -> list[OscItem]:
    """Construit la liste ordonnée (adresse, valeur) à envoyer à la console.

    Adressage niveau feuille, garantissant de ne toucher que les paramètres
    présents dans le preset. L'ordre suit PUSH_ORDER : gate en dernier.
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
        elif block == "hpf" and obj is not None:
            items.append((f"{prefix}/preamp/hpon", int(obj.on)))
            items.append((f"{prefix}/preamp/hpf", obj.freq))
        elif block == "eq" and obj is not None:
            items.append((f"{prefix}/eq/on", 1))
            for band in sorted(obj, key=lambda b: b.band):
                base = f"{prefix}/eq/{band.band}"
                items.append((f"{base}/type", band.type))
                items.append((f"{base}/f", band.freq))
                items.append((f"{base}/g", band.gain))
                items.append((f"{base}/q", band.q))
        elif block == "comp" and obj is not None:
            base = f"{prefix}/dyn"
            items.append((f"{base}/on", int(obj.on)))
            items.append((f"{base}/thr", obj.thr))
            items.append((f"{base}/ratio", obj.ratio))
            items.append((f"{base}/attack", obj.attack))
            items.append((f"{base}/release", obj.release))
            items.append((f"{base}/knee", obj.knee))
            items.append((f"{base}/mgain", obj.mgain))
            items.append((f"{base}/mix", obj.mix))
        elif block == "gate" and obj is not None:
            base = f"{prefix}/gate"
            items.append((f"{base}/on", int(obj.on)))
            items.append((f"{base}/thr", obj.thr))
            items.append((f"{base}/range", obj.range))
            items.append((f"{base}/attack", obj.attack))
            items.append((f"{base}/hold", obj.hold))
            items.append((f"{base}/release", obj.release))
    return items


def capture_nodes(channel: int) -> list[str]:
    """Nœuds à interroger pour « Aspirer la tranche » (une requête, plusieurs valeurs).

    Ordre = PUSH_ORDER assumé ; à l'arrivée, snapshot_values() décode chaque
    réponse par position via NODE_FIELDS.
    """
    prefix = channel_prefix(channel)
    nodes = [
        f"{prefix}/config",
        f"{prefix}/preamp",
        f"{prefix}/eq",
    ]
    nodes.extend(f"{prefix}/eq/{band}" for band in range(1, 5))
    nodes.append(f"{prefix}/dyn")
    nodes.append(f"{prefix}/gate")
    return nodes


def snapshot_to_preset_values(replies: dict[str, list[Any]], prefix: str) -> dict[str, Any]:
    """Décode les réponses de nœud (listes positionnelles) en dictionnaire de preset.

    - le « trim » du preamp (position 1) est volontairement ignoré : c'est le
      gain d'entrée, jamais aspiré ni repoussé par InspireAir ;
    - le mode du gate, sa clef (keysrc), et les champs sources de config sont
      capturés à titre informatif mais n'entrent pas dans le preset.
    """
    preset_values: dict[str, Any] = {}
    eq_bands: list[dict[str, Any]] = []
    for node_address, values in sorted(replies.items()):
        rel = node_address.removeprefix(prefix).strip("/")
        if rel.startswith("eq/") and rel.count("/") == 1:
            band_no = int(rel.split("/")[1])
            fields = NODE_FIELDS["eq/{band}"]
            if len(values) < len(fields):
                continue
            band: dict[str, Any] = {"band": band_no, "type": str(values[0])}
            band["freq"] = round(float(values[1]), 2)
            band["gain"] = round(float(values[2]), 2)
            band["q"] = round(float(values[3]), 2)
            eq_bands.append(band)
            continue
        fields = NODE_FIELDS.get(rel)
        if fields is None:
            continue
        entry: dict[str, Any] = {}
        for name, value in zip(fields, values):
            if name in ("insrc", "rtnsrc", "trim", "rtnsw"):
                continue
            if name == "mode" and rel in ("gate", "dyn"):
                continue
            if name == "keysrc":
                continue
            if name == "auto":
                continue
            if isinstance(value, str) and value.upper() in ("ON", "OFF", "YES", "NO"):
                entry[name] = value.upper() in ("ON", "YES")
            else:
                entry[name] = value
        if rel == "config":
            if entry.get("name", "") and entry["name"] != '"':
                preset_values["config"] = {
                    "name": str(entry.get("name", "")).strip('"'),
                    "color": int(entry.get("color", 0)),
                }
        elif rel == "preamp":
            hpf_entry = {"on": bool(entry.get("hpon", False))}
            if entry.get("hpf") is not None:
                hpf_entry["freq"] = round(float(entry["hpf"]), 2)
            preset_values["hpf"] = hpf_entry
        elif rel == "gate":
            gate = {"on": bool(entry.get("on", False))}
            gate.update(
                {
                    key: round(float(entry[key]), 3)
                    for key in ("thr", "range", "attack", "hold", "release")
                    if key in entry and entry[key] is not None
                }
            )
            preset_values["gate"] = gate
        elif rel == "dyn":
            comp = {
                "on": bool(entry.get("on", False)),
                "ratio": float(entry.get("ratio", 4.0)),
                "knee": float(entry.get("knee", 0.0)),
                "mgain": round(float(entry.get("mgain", 0.0)), 2),
                "mix": round(float(entry.get("mix", 100.0)), 2),
            }
            comp.update(
                {
                    key: round(float(entry[key]), 3)
                    for key in ("thr", "attack", "release")
                    if key in entry and entry[key] is not None
                }
            )
            preset_values["comp"] = comp
        elif rel == "eq":
            preset_values["eq_on"] = bool(entry.get("on", False))
    if eq_bands:
        preset_values["eq"] = sorted(eq_bands, key=lambda b: b["band"])
    preset_values.pop("eq_on", None)
    return preset_values
