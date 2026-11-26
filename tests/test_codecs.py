"""Certification des codecs filaires : paires connues (dump XR18 + code Maillot)
et aller-retour encode/decode quantifié.
"""

import pytest

from inspireair.codecs import decode_value, encode_value
from inspireair.oscmap import preset_to_osc
from inspireair.model import Comp, EqBand, Gate, Hpf, Preset


def test_known_wire_pairs() -> None:
    assert decode_value("preamp", "hpf", 0.82) == pytest.approx(233.3, abs=0.5)
    assert decode_value("gate", "thr", 0.09375) == pytest.approx(-72.5)
    assert decode_value("gate", "range", 0.7894736842) == pytest.approx(48.0)
    assert decode_value("gate", "attack", 1 / 24) == pytest.approx(5.0)
    assert decode_value("dyn", "thr", 0.1833333333) == pytest.approx(-49.0)
    assert decode_value("eq", "f", 0.265) == pytest.approx(124.7, abs=0.2)
    assert decode_value("eq", "q", 0.4647887324) == pytest.approx(1.96, abs=0.01)
    assert decode_value("eq", "g", 0.5) == 0.0
    assert decode_value("dyn", "mix", 1.0) == 100.0
    assert decode_value("eq", "type", 2) == "PEQ"


def test_ratio_list_is_zero_based() -> None:
    assert decode_value("dyn", "ratio", 7) == 5.0
    assert encode_value("dyn", "ratio", 5.0) == 7
    assert decode_value("dyn", "ratio", 0) == 1.1
    assert decode_value("dyn", "ratio", 11) == 100.0


def test_encode_quantizes_to_console_steps() -> None:
    assert encode_value("preamp", "hpf", 100.0) == pytest.approx(0.54)
    assert encode_value("eq", "f", 200.0) == pytest.approx(0.335)
    assert encode_value("eq", "q", 2.0) == pytest.approx(33 / 71, abs=1e-9)
    assert encode_value("gate", "attack", 1.0) == pytest.approx(1 / 120, abs=1e-9)
    assert encode_value("dyn", "mix", 100.0) == 1.0
    assert encode_value("dyn", "mix", 50.0) == 0.5


@pytest.mark.parametrize(
    "node,field,value",
    [
        ("preamp", "hpf", 120.0),
        ("gate", "thr", -28.0),
        ("gate", "range", 18.0),
        ("gate", "attack", 1.0),
        ("gate", "hold", 15.0),
        ("gate", "release", 120.0),
        ("dyn", "thr", -16.0),
        ("dyn", "knee", 2.0),
        ("dyn", "mgain", 3.0),
        ("dyn", "attack", 12.0),
        ("dyn", "release", 90.0),
        ("dyn", "mix", 30.0),
        ("eq", "f", 3500.0),
        ("eq", "g", 3.5),
        ("eq", "q", 1.8),
    ],
)
def test_roundtrip_encode_decode(node: str, field: str, value: float) -> None:
    wire = encode_value(node, field, value)
    assert decode_value(node, field, wire) == pytest.approx(value, rel=0.07, abs=0.5)


def test_preset_to_osc_emits_wire_values() -> None:
    preset = Preset(
        instrument="Batterie",
        element="Caisse claire",
        style="Rock punchy",
        hpf=Hpf(on=True, freq=100.0),
        eq=[EqBand(band=1, type="PEQ", freq=200, gain=3.5, q=2.0)],
        comp=Comp(on=True, thr=-16.0, ratio=4.0, attack=12, release=90, mgain=3.0, mix=30.0),
        gate=Gate(on=True, thr=-28.0, range=18.0, attack=1, hold=15, release=120),
    )
    items = dict(preset_to_osc(preset, 3))
    assert items["/ch/03/preamp/hpf"] == pytest.approx(0.54)
    assert items["/ch/03/eq/1/type"] == 2
    assert items["/ch/03/eq/1/f"] == pytest.approx(0.335)
    assert items["/ch/03/eq/1/q"] == pytest.approx(33 / 71, abs=1e-9)
    assert items["/ch/03/dyn/ratio"] == 6
    assert items["/ch/03/dyn/mix"] == pytest.approx(0.3)
    assert items["/ch/03/gate/thr"] == pytest.approx(0.65)
    assert items["/ch/03/gate/release"] == pytest.approx(0.48)
