"""Nickel concentration from an EDTA titration."""

from __future__ import annotations

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
    apparent = (
        titrant_ml / 1000.0 * molarity * NICKEL_G_PER_MOL / (sample_ml / 1000.0)
    )
    return apparent * dilution_factor - copper_g_l * NICKEL_G_PER_MOL / COPPER_G_PER_MOL
