from pathlib import Path

import pytest

from inspireair.model import Comp, Gate, Hpf, Preset, PresetError

ROOT = Path(__file__).resolve().parents[1]


def sample_preset() -> Preset:
    return Preset.from_dict(
        {
            "instrument": "Batterie",
            "element": "Caisse claire",
            "variant": "Top",
            "style": "Rock punchy",
            "hpf": {"on": True, "freq": 100},
            "gate": {"on": True, "thr": -28.0, "range": 18.0, "attack": 1, "hold": 15, "release": 120},
            "eq": [{"band": 1, "type": "PEQ", "freq": 200, "gain": 3.5, "q": 2.0}],
            "comp": {"on": True, "thr": -16.0, "ratio": 4.0, "attack": 12, "release": 90, "mgain": 3.0},
        }
    )


def test_roundtrip_dict() -> None:
    preset = sample_preset()
    again = Preset.from_dict(preset.to_dict())
    assert again == preset


def test_blocks_and_filtering() -> None:
    preset = sample_preset()
    assert preset.blocks() == {"hpf", "gate", "eq", "comp"}
    only_eq = preset.keep_blocks({"eq"})
    assert only_eq.blocks() == {"eq"}
    assert only_eq.gate is None and only_eq.comp is None and only_eq.hpf is None
    only_gate = preset.keep_blocks({"gate"})
    assert only_gate.gate == preset.gate
    with pytest.raises(PresetError):
        preset.keep_blocks({"fader"})


def test_validation_ranges() -> None:
    with pytest.raises(PresetError):
        Hpf(on=True, freq=5000.0).validated()
    with pytest.raises(PresetError):
        Gate(thr=-120.0).validated()
    with pytest.raises(PresetError):
        Comp(ratio=64.0).validated()
    gate = Gate(thr=-28.0, attack=1).validated()
    assert gate.range == 18.0


def test_gate_sent_last_and_headamp_excluded() -> None:
    from inspireair.oscmap import preset_to_osc

    items = preset_to_osc(sample_preset(), 2)
    addresses = [a for a, _ in items]
    last_of = lambda base: max(i for i, a in enumerate(addresses) if a.startswith(base))  # noqa: E731
    assert last_of("/ch/02/hpf/") < last_of("/ch/02/eq/") < last_of("/ch/02/comp/") < last_of("/ch/02/gate/")
    assert addresses[-1] == "/ch/02/gate/rel"
    assert all(not a.startswith("/ch/02/pre/") for a in addresses)
    assert all("/mix/" not in a for a in addresses)


def test_describe_is_human_readable() -> None:
    text = sample_preset().describe()
    assert "3-4 kHz" not in text
    assert "Hz" in text
    assert "Coupe les fréquences sous" in text


def test_channels_17_18_use_rtn_aux() -> None:
    from inspireair.oscmap import channel_prefix, preset_to_osc

    assert channel_prefix(17) == "/rtn/aux"
    items = preset_to_osc(instrument_preset(), 17)
    assert items[0][0].startswith("/rtn/aux/")


def instrument_preset() -> Preset:
    return Preset(instrument="Claviers", element="Synthés", style="Pop moderne", hpf=Hpf())


def test_variants_and_tessiture_fields_only() -> None:
    from inspireair.taxonomy import PAIR_ELEMENTS, TESSITURES, VARIANTS

    assert VARIANTS["Grosse caisse"] == ["Micro unique", "Batte", "Résonance"]
    assert set(TESSITURES) == {"Homme", "Femme"}
    assert "Overhead" in PAIR_ELEMENTS
