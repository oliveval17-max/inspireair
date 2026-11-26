"""Undo / Comparer / Kit : snapshots, diff filaire demi-cran, plan de kit.

Aucune console nécessaire : les réponses utilisent le dump réel du canal 1
(scène FMR, XR18 fw 1.19).
"""

from pathlib import Path

import pytest

from inspireair.kit import load_kit
from inspireair.model import Preset
from inspireair.snapshot import (
    capture_leaf_values,
    capture_snapshot,
    compare_preset,
    load_snapshot,
    restore_items,
    undo_path,
)
from inspireair.oscmap import snapshot_to_preset_values

FMR_REPLIES = {
    "/ch/01/config": ["Overhd G", 4, 0, 0],
    "/ch/01/preamp": [0.5, 0, 1, 1, 0.8199999928474426],
    "/ch/01/gate": [1, 3, 0.09375, 0.7894737124443054, 0.0416666679084301, 0.6399999856948853, 0.7200000286102295, 0],
    "/ch/01/dyn": [1, 0, 0, 1, 0.18333333730697632, 7, 0.20000000298023224, 0.0, 0.15000000596046448, 0.46000000834465027, 0.4099999964237213, 1.0, 0, 0],
    "/ch/01/eq": [1],
    "/ch/01/eq/1": [2, 0.26499998569488525, 0.5, 0.4647887349128723],
}


class FakeClient:
    host = "192.0.2.10"

    def __init__(self, replies: dict[str, list]) -> None:
        self._replies = replies

    def capture(self, channel: int, nodes=None) -> dict[str, list]:
        return {node: list(values) for node, values in self._replies.items()}


def fmr_preset() -> Preset:
    values = snapshot_to_preset_values(FMR_REPLIES, "/ch/01")
    return Preset.from_dict(
        {"instrument": "Capture", "element": "Canal 1", "style": "Balance capturée", **values}
    ).validated()


def test_undo_path_and_snapshot_roundtrip(tmp_path: Path) -> None:
    path = capture_snapshot(FakeClient(FMR_REPLIES), 1, directory=tmp_path)
    assert path == undo_path(1, tmp_path) and path.exists()
    payload = load_snapshot(path)
    assert payload["channel"] == 1 and payload["host"] == "192.0.2.10"
    assert payload["values"]["config"] == {"name": "Overhd G", "color": 4}


def test_restore_items_gate_last_and_no_forbidden(tmp_path: Path) -> None:
    path = capture_snapshot(FakeClient(FMR_REPLIES), 1, directory=tmp_path)
    items = restore_items(path)
    addresses = [address for address, _ in items]
    assert addresses[-1].startswith("/ch/01/gate/")
    assert all("/headamp" not in a and "/preamp/trim" not in a and "/mix/" not in a for a in addresses)


def test_capture_leaf_values_flattens_nodes() -> None:
    leaves = capture_leaf_values(FMR_REPLIES, "/ch/01")
    assert leaves["/ch/01/preamp/hpf"] == pytest.approx(0.82)
    assert leaves["/ch/01/eq/1/type"] == 2
    assert leaves["/ch/01/config/name"] == "Overhd G"


def test_compare_preset_conforme_au_demcran() -> None:
    assert compare_preset(fmr_preset(), FMR_REPLIES, 1) == []


def test_compare_preset_detecte_les_ecarts() -> None:
    preset = fmr_preset()
    preset.gate.thr = -40.0
    diffs = compare_preset(preset, FMR_REPLIES, 1)
    assert any("/ch/01/gate/thr" in diff for diff in diffs)
    assert len(diffs) == 1


def test_compare_respecte_les_blocs_demandes() -> None:
    preset = fmr_preset()
    preset.gate.thr = -40.0
    assert compare_preset(preset, FMR_REPLIES, 1, blocks={"eq"}) == []


def test_load_kit_plan(tmp_path: Path) -> None:
    preset_path = Path(__file__).resolve().parents[1] / "presets" / "batterie"
    source = next(preset_path.glob("grosse-caisse-*.yaml"))
    kit_file = tmp_path / "kit.yaml"
    kit_file.write_text(
        f"entries:\n  - channel: 1\n    preset: {source}\n  - channel: 2\n    preset: {source}\n",
        encoding="utf-8",
    )
    plan = load_kit(kit_file)
    assert [channel for channel, _ in plan] == [1, 2]
    assert all(preset.element for _, preset in plan)


def test_load_kit_rejete_kit_vide(tmp_path: Path) -> None:
    kit_file = tmp_path / "kit.yaml"
    kit_file.write_text("entries: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="entries"):
        load_kit(kit_file)
