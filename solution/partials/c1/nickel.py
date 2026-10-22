"""Nickel concentration from an EDTA titration."""

from __future__ import annotations

import math

from .constants import COPPER_G_PER_MOL, NICKEL_G_PER_MOL


def nickel_concentration_g_l(
    sample_ml: float,
    titrant_ml: float,
    blank_ml: float,
    molarity: float,
    dilution_factor: float,
    copper_g_l: float,
) -> float:
    """Return nickel concentration in grams per litre."""
    sample_ml = float(sample_ml)
    titrant_ml = float(titrant_ml)
    blank_ml = float(blank_ml)
    molarity = float(molarity)
    dilution_factor = float(dilution_factor)
    copper_g_l = float(copper_g_l)
    values = (sample_ml, titrant_ml, blank_ml, molarity, dilution_factor, copper_g_l)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("nickel titration values must be finite")
    if sample_ml <= 0 or molarity <= 0 or dilution_factor <= 0:
        raise ValueError(
            "sample volume, titrant molarity and dilution factor must be positive"
        )
    if copper_g_l < 0:
        raise ValueError("copper concentration must not be negative")
    if blank_ml < 0 or titrant_ml < blank_ml:
        raise ValueError("blank volume must be between zero and titrant volume")
    net_ml = titrant_ml - blank_ml
    apparent = (
        net_ml / 1000.0
        * molarity
        * NICKEL_G_PER_MOL
        / (sample_ml / 1000.0)
        * dilution_factor
    )
    corrected = apparent - copper_g_l * NICKEL_G_PER_MOL / COPPER_G_PER_MOL
    if corrected < -1e-12:
        raise ValueError("copper correction exceeds the apparent nickel concentration")
    return max(0.0, corrected)
