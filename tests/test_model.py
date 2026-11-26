from pathlib import Path

import pytest

from inspireair.model import Comp, EqBand, Gate, Hpf, Preset, PresetError

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
        Gate(range=140.0).validated()
    with pytest.raises(PresetError):
        Comp(ratio=8.0).validated()
    with pytest.raises(PresetError):
        Comp(mgain=-3.0).validated()
    gate = Gate(thr=-28.0, attack=1).validated()
    assert gate.range == 18.0
    comp = Comp().validated()
    assert comp.ratio == 4.0
    alias = EqBand(type="VEQ6").validated()
    assert alias.type == "VEQ"


def test_gate_sent_last_and_headamp_excluded() -> None:
    from inspireair.oscmap import preset_to_osc

    items = preset_to_osc(sample_preset(), 2)
    addresses = [a for a, _ in items]
    last_of = lambda base: max(i for i, a in enumerate(addresses) if a.startswith(base))  # noqa: E731
    assert last_of("/ch/02/preamp/hp") < last_of("/ch/02/eq/") < last_of("/ch/02/dyn/") < last_of("/ch/02/gate/")
    assert addresses[-1] == "/ch/02/gate/release"
    assert all(not a.startswith("/headamp") for a in addresses)
    assert all("/preamp/trim" not in a for a in addresses)
    assert all("/mix/" not in a for a in addresses)


def test_snapshot_decode_ignores_trim_and_sources() -> None:
    """Dump réel canal 1 (scène FMR, XR18 fw 1.19) : valeurs filaires 0..1."""
    import pytest

    from inspireair.oscmap import snapshot_to_preset_values

    replies = {
        "/ch/01/config": ["Overhd G", 4, 0, 0],
        "/ch/01/preamp": [0.5, 0, 1, 1, 0.8199999928474426],
        "/ch/01/gate": [1, 3, 0.09375, 0.7894737124443054, 0.0416666679084301, 0.6399999856948853, 0.7200000286102295, 0],
        "/ch/01/dyn": [1, 0, 0, 1, 0.18333333730697632, 7, 0.20000000298023224, 0.0, 0.15000000596046448, 0.46000000834465027, 0.4099999964237213, 1.0, 0, 0],
        "/ch/01/eq": [1],
        "/ch/01/eq/1": [2, 0.26499998569488525, 0.5, 0.4647887349128723],
    }
    values = snapshot_to_preset_values(replies, "/ch/01")
    assert values["config"] == {"name": "Overhd G", "color": 4}
    assert values["hpf"] == {"on": True, "freq": pytest.approx(233.3, abs=0.5)}
    assert values["gate"]["on"] is True
    assert values["gate"]["thr"] == pytest.approx(-72.5)
    assert values["gate"]["range"] == pytest.approx(48.0)
    assert values["gate"]["attack"] == pytest.approx(5.0)
    assert values["gate"]["hold"] == pytest.approx(31.7, abs=0.3)
    assert values["gate"]["release"] == pytest.approx(615.4, abs=1.0)
    assert values["comp"]["on"] is True
    assert values["comp"]["thr"] == pytest.approx(-49.0)
    assert values["comp"]["ratio"] == 5.0
    assert values["comp"]["knee"] == pytest.approx(1.0)
    assert values["comp"]["mgain"] == 0.0
    assert values["comp"]["attack"] == pytest.approx(18.0)
    assert values["comp"]["hold"] == pytest.approx(4.0, abs=0.2)
    assert values["comp"]["release"] == pytest.approx(77.4, abs=0.5)
    assert values["comp"]["mix"] == pytest.approx(100.0)
    assert values["eq"][0] == {
        "band": 1,
        "type": "PEQ",
        "freq": pytest.approx(124.7, abs=0.2),
        "gain": 0.0,
        "q": pytest.approx(1.96, abs=0.01),
    }
    assert "preamp" not in values
    assert "eq_on" not in values


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
