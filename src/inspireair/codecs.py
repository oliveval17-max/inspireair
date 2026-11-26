"""Conversion grandeurs réelles <-> valeurs filaires normalisées de la console.

La console X-Air transmet sur OSC des valeurs normalisées 0..1, quantifiées
aux crans hardware. Formules certifiées depuis le code de référence
XAirSetScene / Xscene2X.c (P. Maillot / K. Mitchell) et un dump réel
(XR18 fw 1.19) :

- ``Xp_linf(xmin, span, step)``  : wire = round((v - xmin)/span · span/step) / (span/step) ;
- ``Xp_logf(xmin, lspan, n)``    : wire = round(ln(v/xmin)/lspan · n) / n ;
- ``Xp_frequency(nsteps)``       : wire = round(ln(v/20)/ln(1000) · nsteps) / nsteps ;
- ``Xp_percent``                 : wire = v/100 (1.0 = 100 %) ;
- ``Xp_list``                    : wire = index 0-based dans la liste.

Contre-vérifications terrain (canal 1, scène FMR) : hpf 0.82 -> 233 Hz,
gate thr 0.09375 -> -72.5 dB, range 0.789474 -> 48 dB, dyn ratio 7 -> 5.0,
eq f 0.265 -> 124.7 Hz, eq q 0.464789 -> ~2.0.
"""

from __future__ import annotations

import math
from typing import Callable, Union

from .model import COMP_RATIOS, EQ_TYPES, EQ_TYPE_ALIASES

CodecValue = Union[float, int, str]

LN_1000 = 6.907755278982137          # ln(20000/20)
LN_HPF = 2.995732273553991           # ln(400/20)
LN_HOLD = 11.512925464970229         # ln(2000/0.02)
LN_RELEASE = 6.684611727667927       # ln(4000/5)
LN_Q = -3.506557897319982            # ln(0.3/10)

_EQ_TYPE_ALIASES_UPPER = {k.upper(): v for k, v in EQ_TYPE_ALIASES.items()}


def _clamp01(x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _quantize(x: float, steps: float) -> float:
    return round(x * steps) / steps


def _lin_encode(value: float, xmin: float, span: float, step: float) -> float:
    steps = span / step
    return _quantize(_clamp01((value - xmin) / span), steps)


def _lin_decode(wire: float, xmin: float, span: float) -> float:
    return xmin + span * wire


def _log_encode(value: float, xmin: float, lspan: float, nsteps: int) -> float:
    if value <= 0:
        raise ValueError(f"valeur {value} invalide pour une échelle logarithmique")
    return _quantize(_clamp01(math.log(value / xmin) / lspan), nsteps)


def _log_decode(wire: float, xmin: float, lspan: float) -> float:
    return xmin * math.exp(lspan * wire)


def _ratio_encode(value: float) -> int:
    return min(range(len(COMP_RATIOS)), key=lambda i: abs(COMP_RATIOS[i] - value))


def _ratio_decode(wire: float) -> float:
    return COMP_RATIOS[int(round(wire))]


def _eq_type_encode(value: CodecValue) -> int:
    name = str(value).strip().upper()
    name = _EQ_TYPE_ALIASES_UPPER.get(name, name)
    try:
        return EQ_TYPES.index(name)
    except ValueError:
        raise ValueError(f"type EQ inconnu : {value!r} (attendus : {EQ_TYPES})") from None


def _eq_type_decode(wire: float) -> str:
    return EQ_TYPES[int(round(wire))]


def _hpf_encode(value: float) -> float:
    return _log_encode(value, 20.0, LN_HPF, 100)


def _hpf_decode(wire: float) -> float:
    return _log_decode(wire, 20.0, LN_HPF)


def _eq_f_encode(value: float) -> float:
    return _log_encode(value, 20.0, LN_1000, 200)


def _eq_f_decode(wire: float) -> float:
    return 20.0 * 1000.0**wire


def _hold_encode(value: float) -> float:
    return _log_encode(value, 0.02, LN_HOLD, 100)


def _hold_decode(wire: float) -> float:
    return _log_decode(wire, 0.02, LN_HOLD)


def _release_encode(value: float) -> float:
    return _log_encode(value, 5.0, LN_RELEASE, 100)


def _release_decode(wire: float) -> float:
    return _log_decode(wire, 5.0, LN_RELEASE)


# (nœud, champ) -> (encode réel -> filaire, decode filaire -> réel).
# Les champs absents de cette table transitent sans conversion (ints 0/1,
# noms de tranche...).
CODECS: dict[tuple[str, str], tuple[Callable[[CodecValue], CodecValue], Callable[[float], CodecValue]]] = {
    ("preamp", "hpf"): (_hpf_encode, _hpf_decode),
    ("gate", "thr"): (
        lambda v: _lin_encode(v, -80.0, 80.0, 0.5),
        lambda x: _lin_decode(x, -80.0, 80.0),
    ),
    ("gate", "range"): (
        lambda v: _lin_encode(v, 3.0, 57.0, 1.0),
        lambda x: _lin_decode(x, 3.0, 57.0),
    ),
    ("gate", "attack"): (
        lambda v: _lin_encode(v, 0.0, 120.0, 1.0),
        lambda x: _lin_decode(x, 0.0, 120.0),
    ),
    ("gate", "hold"): (_hold_encode, _hold_decode),
    ("gate", "release"): (_release_encode, _release_decode),
    ("dyn", "thr"): (
        lambda v: _lin_encode(v, -60.0, 60.0, 0.5),
        lambda x: _lin_decode(x, -60.0, 60.0),
    ),
    ("dyn", "ratio"): (_ratio_encode, _ratio_decode),
    ("dyn", "knee"): (
        lambda v: _lin_encode(v, 0.0, 5.0, 1.0),
        lambda x: _lin_decode(x, 0.0, 5.0),
    ),
    ("dyn", "mgain"): (
        lambda v: _lin_encode(v, 0.0, 24.0, 0.5),
        lambda x: _lin_decode(x, 0.0, 24.0),
    ),
    ("dyn", "attack"): (
        lambda v: _lin_encode(v, 0.0, 120.0, 1.0),
        lambda x: _lin_decode(x, 0.0, 120.0),
    ),
    ("dyn", "hold"): (_hold_encode, _hold_decode),
    ("dyn", "release"): (_release_encode, _release_decode),
    ("dyn", "mix"): (
        lambda v: v / 100.0,
        lambda x: x * 100.0,
    ),
    ("eq", "type"): (_eq_type_encode, _eq_type_decode),
    ("eq", "f"): (_eq_f_encode, _eq_f_decode),
    ("eq", "g"): (
        lambda v: _lin_encode(v, -15.0, 30.0, 0.25),
        lambda x: _lin_decode(x, -15.0, 30.0),
    ),
    ("eq", "q"): (
        lambda v: _log_encode(v, 10.0, LN_Q, 71),
        lambda x: _log_decode(x, 10.0, LN_Q),
    ),
}


def encode_value(node: str, field: str, value: CodecValue) -> CodecValue:
    """Grandeur réelle -> valeur filaire normalisée (push)."""
    codec = CODECS.get((node, field))
    if codec is None:
        return value
    return codec[0](value)


def decode_value(node: str, field: str, wire: CodecValue) -> CodecValue:
    """Valeur filaire normalisée -> grandeur réelle (grab)."""
    codec = CODECS.get((node, field))
    if codec is None:
        return wire
    return codec[1](float(wire))
