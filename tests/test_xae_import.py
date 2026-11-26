from inspireair.model import Preset
from inspireair.xae_import import chn_to_preset_values, finalize_preset, preset_to_chn_lines

CHN_SAMPLE = """
# X-Air Edit channel preset (ancienne forme feuille, une valeur par ligne)
/ch/03/config/name "Slap Top"
/ch/03/config/color 3
/ch/03/hpf/on 1
/ch/03/hpf/freq 110.0
/ch/03/gate/on 1
/ch/03/gate/thr -30.0
/ch/03/gate/rng 20.0
/ch/03/gate/att 1.0
/ch/03/gate/hold 10.0
/ch/03/gate/rel 100.0
/ch/03/eq/1/type PEQ
/ch/03/eq/1/freq 210.0
/ch/03/eq/1/g 3.0
/ch/03/eq/1/q 1.8
/ch/03/comp/on 1
/ch/03/comp/thr -18.0
/ch/03/comp/ratio 3.0
/ch/03/comp/att 15.0
/ch/03/comp/rel 120.0
/ch/03/comp/mgain 2.0
/ch/03/mix/fader -12.0
/ch/03/mix/on 1
/ch/04/pre/trim 15.0
"""

# Export réel X-Air Edit (tranche HiHat, forme strip agrégée) : /mix, trim,
# side-chain et keysrc doivent être ignorés ; « 4k52 » = 4520 Hz.
CHN_REAL_HIHAT = """
/config/name "HiHat"
/config/color 4
/preamp +0.0 OFF OFF ON 248
/gate ON GATE -74.5 60.0 5 50.2 504 SELF
/gate/filter ON 5.0 4k52
/eq ON
/eq/1 PEQ 124.7 +0.00 2.0
/eq/2 PEQ 863.0 -2.50 2.0
/eq/3 PEQ 4k52 +14.5 2.0
/eq/4 HShv 9k35 +15.0 2.0
/dyn ON COMP PEAK LOG -53.0 4.0 5 0.00 10 10.0 151 100 SELF OFF
/dyn/filter ON 5.0 7k34
/mix ON  -4.3 ON -90
/mix/01 -14.5 OFF PREEQ +0
/mix/02 -23.0 OFF PREEQ
/mix/03  -6.8 OFF PREEQ +0
/mix/04 -14.0 OFF PREEQ
/mix/05 -23.0 OFF PREEQ +0
/mix/06  -1.5 OFF PREEQ
/mix/07   -oo OFF IN
/mix/08   -oo OFF IN
/mix/09   -oo OFF IN
/mix/10   -oo OFF IN
"""


def test_import_ignores_fader_and_other_channels() -> None:
    values = chn_to_preset_values(CHN_SAMPLE, channel=3)
    assert "hpf" in values and "gate" in values
    assert values["hpf"]["freq"] == 110.0
    assert values["gate"]["range"] == 20.0
    assert values["config"]["name"] == "Slap Top"


def test_finalize_produces_valid_preset() -> None:
    preset = finalize_preset(chn_to_preset_values(CHN_SAMPLE, channel=3))
    assert preset.element == "Importé"
    assert preset.eq[0].freq == 210.0
    assert preset.comp.thr == -18.0


def test_import_real_hihat_strip() -> None:
    values = chn_to_preset_values(CHN_REAL_HIHAT, channel=10)
    assert values["config"] == {"name": "HiHat", "color": 4}
    assert values["hpf"] == {"on": True, "freq": 248.0}
    assert values["gate"] == {
        "on": True,
        "thr": -74.5,
        "range": 60.0,
        "attack": 5.0,
        "hold": 50.2,
        "release": 504.0,
    }
    assert values["comp"] == {
        "on": True,
        "thr": -53.0,
        "ratio": 4.0,
        "knee": 5.0,
        "mgain": 0.0,
        "attack": 10.0,
        "hold": 10.0,
        "release": 151.0,
        "mix": 100.0,
    }
    assert values["eq"] == [
        {"band": 1, "type": "PEQ", "freq": 124.7, "gain": 0.0, "q": 2.0},
        {"band": 2, "type": "PEQ", "freq": 863.0, "gain": -2.5, "q": 2.0},
        {"band": 3, "type": "PEQ", "freq": 4520.0, "gain": 14.5, "q": 2.0},
        {"band": 4, "type": "HShv", "freq": 9350.0, "gain": 15.0, "q": 2.0},
    ]


def test_import_real_hihat_finalizes_and_validates() -> None:
    preset = finalize_preset(chn_to_preset_values(CHN_REAL_HIHAT, channel=10))
    assert preset.config.name == "HiHat"
    assert preset.eq[2].freq == 4520.0
    assert preset.gate.release == 504.0


def test_export_omits_preamp_and_never_touches_gain() -> None:
    preset = finalize_preset(chn_to_preset_values(CHN_SAMPLE, channel=3))
    lines = preset_to_chn_lines(preset, 3)
    data_lines = [line for line in lines if not line.startswith("#")]
    text = "\n".join(data_lines)
    assert "/preamp" not in text and "trim" not in text
    assert all("/mix" not in line for line in lines)
    assert any(line.startswith("/gate ") for line in lines)
    assert any(line.startswith("/dyn ") for line in lines)
    assert any(line.startswith("/eq/1 ") for line in lines)


def test_export_import_roundtrip_strip_form() -> None:
    preset = finalize_preset(chn_to_preset_values(CHN_REAL_HIHAT, channel=10))
    lines = preset_to_chn_lines(preset, 10)
    text = "\n".join(lines)
    values = chn_to_preset_values(text, channel=10)
    assert values["config"] == {"name": "HiHat", "color": 4}
    assert values["gate"]["thr"] == -74.5
    assert values["comp"]["ratio"] == 4.0
    assert values["eq"][3]["type"] == "HShv" and values["eq"][3]["freq"] == 9350.0
