from pathlib import Path

import pytest

from inspireair.storage import load_preset, save_preset, schema_errors

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "path",
    sorted((ROOT / "presets").rglob("*.yaml")) + sorted((ROOT / "presets").rglob("*.yml")) + sorted((ROOT / "presets").rglob("*.json")),
)
def test_shipped_presets_validate(path: Path) -> None:
    assert schema_errors(path) == []
    preset = load_preset(path)
    assert preset.instrument in (
        "Batterie",
        "Percussions",
        "Guitares",
        "Claviers",
        "Cuivres & Vents",
        "Voix",
        "Capture",
        "Import",
    )


def test_yaml_json_roundtrip(tmp_path: Path) -> None:
    preset = load_preset(ROOT / "presets" / "batterie" / "caisse-claire-top-rock-punchy.yaml")
    json_path = save_preset(preset, tmp_path / "x.json", fmt="json")
    yaml_path = save_preset(preset, tmp_path / "x.yaml", fmt="yaml")
    assert load_preset(json_path) == preset
    assert load_preset(yaml_path) == preset


def test_schema_rejects_bad_type(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "instrument: Batterie\nelement: Grosse caisse\nstyle: Funk sec\n"
        "hpf:\n  on: true\n  freq: not-a-number\n",
        encoding="utf-8",
    )
    assert schema_errors(bad)
