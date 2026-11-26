"""Annuler / Comparer : snapshot d'une tranche avant push, restauration, diff.

Sécurité live : chaque push sauvegarde d'abord l'état courant du canal
(« undo ») ; `inspireair undo` le rejoue tel quel, `inspireair compare`
explique les écarts entre un preset et la console. Les comparaisons se font
en valeurs filaires avec une tolérance d'un demi-cran (quantisation console).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

import yaml

from .codecs import wire_epsilon
from .model import Preset
from .oscmap import NODE_FIELDS, OscItem, channel_prefix, preset_to_osc, snapshot_to_preset_values

DEFAULT_SNAPSHOT_DIR = Path.home() / ".inspireair" / "snapshots"


class CapturingClient(Protocol):
    host: str

    def capture(self, channel: int, nodes: Optional[list[str]] = None) -> dict[str, list[Any]]: ...


def undo_path(channel: int, directory: Optional[Path] = None) -> Path:
    base = Path(directory) if directory else DEFAULT_SNAPSHOT_DIR
    return base / f"undo-ch{channel:02d}.yaml"


def capture_snapshot(client: CapturingClient, channel: int, directory: Optional[Path] = None) -> Path:
    """Capture l'état courant du canal et l'écrit dans le fichier undo."""
    replies = client.capture(channel)
    values = snapshot_to_preset_values(replies, channel_prefix(channel))
    payload = {
        "channel": channel,
        "host": client.host,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "values": values,
    }
    path = undo_path(channel, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def load_snapshot(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "values" not in payload:
        raise ValueError(f"snapshot illisible : {path}")
    return payload


def restore_items(path: Path, channel: Optional[int] = None) -> list[OscItem]:
    """Construit la liste OSC pour rejouer le snapshot (gate en dernier)."""
    payload = load_snapshot(path)
    ch = int(channel if channel is not None else payload.get("channel", 0))
    if not 1 <= ch <= 18:
        raise ValueError(f"canal {ch} hors plage 1-18 dans {path}")
    preset = Preset.from_dict(
        {
            "instrument": "Undo",
            "element": f"Canal {ch}",
            "style": "Snapshot",
            **payload["values"],
        }
    ).validated()
    return preset_to_osc(preset, ch)


def capture_leaf_values(replies: dict[str, list[Any]], prefix: str) -> dict[str, Any]:
    """Aplatit les réponses de nœuds en {adresse feuille OSC : valeur filaire}."""
    leaves: dict[str, Any] = {}
    for node_address, values in replies.items():
        rel = node_address.removeprefix(prefix).strip("/")
        if rel.startswith("eq/") and rel.count("/") == 1:
            fields = NODE_FIELDS["eq/{band}"]
        else:
            fields = NODE_FIELDS.get(rel)
        if not fields:
            continue
        for name, value in zip(fields, values):
            leaves[f"{node_address}/{name}"] = value
    return leaves


def _node_field(address: str, prefix: str) -> tuple[str, str]:
    parts = address.removeprefix(prefix).strip("/").split("/")
    if parts[0] == "eq":
        return "eq", parts[-1]
    return parts[0], parts[1]


def compare_preset(
    preset: Preset,
    replies: dict[str, list[Any]],
    channel: int,
    blocks: Optional[set[str]] = None,
) -> list[str]:
    """Écarts entre ce que le preset enverrait et l'état capturé de la console.

    Comparaison filaire, tolérance = demi-cran : en dessous, c'est de la
    quantisation console, pas une différence réelle.
    """
    prefix = channel_prefix(channel)
    leaves = capture_leaf_values(replies, prefix)
    diffs: list[str] = []
    for address, wanted in preset_to_osc(preset, channel, blocks):
        if address not in leaves:
            diffs.append(f"{address} : absent de la capture console")
            continue
        got = leaves[address]
        node, field = _node_field(address, prefix)
        try:
            got_num = float(got)
            want_num = float(wanted)
        except (TypeError, ValueError):
            if str(got) != str(wanted):
                diffs.append(f"{address} : console {got!r} ≠ preset {wanted!r}")
            continue
        epsilon = wire_epsilon(node, field)
        if abs(got_num - want_num) > epsilon:
            diffs.append(f"{address} : console {got_num:.4f} ≠ preset {want_num:.4f} (tolérance {epsilon:.4f})")
    return diffs
