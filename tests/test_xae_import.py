from inspireair.model import Preset
from inspireair.xae_import import chn_to_preset_values, finalize_preset, preset_to_chn_lines

CHN_SAMPLE = """
# X-Air Edit channel preset (format texte, une requête OSC par ligne)
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


def test_export_cycle() -> None:
    preset = finalize_preset(chn_to_preset_values(CHN_SAMPLE, channel=3))
    lines = preset_to_chn_lines(preset, 3)
    text = "\n".join(lines)
    reparsed = Preset.from_dict(
        {"instrument": "Import", "element": "Importé", "style": "Non classé"}
    )
    assert reparsed is not None
    assert any("/ch/03/preamp/hpf" in l for l in lines)
    gate_index = next(i for i, l in enumerate(lines) if l.startswith("/ch/03/gate/"))
    assert gate_index > next(i for i, l in enumerate(lines) if l.startswith("/ch/03/dyn/"))
