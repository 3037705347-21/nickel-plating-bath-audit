"""Chloride concentration from a silver-nitrate titration."""

from __future__ import annotations

from .constants import CHLORIDE_G_PER_MOL


def chloride_concentration_g_l(
    sample_ml: float,
    titrant_ml: float,
    blank_ml: float,
    molarity: float,
    dilution_factor: float,
) -> float:
    """Return chloride concentration in grams per litre."""
    sample_ml = float(sample_ml)
    titrant_ml = float(titrant_ml)
    blank_ml = float(blank_ml)
    molarity = float(molarity)
    dilution_factor = float(dilution_factor)
    moles = titrant_ml / 1000.0 * molarity
    return moles * CHLORIDE_G_PER_MOL / (sample_ml / 1000.0) * dilution_factor
