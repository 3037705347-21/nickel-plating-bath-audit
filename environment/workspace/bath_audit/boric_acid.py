"""Boric-acid concentration from a mannitol-assisted titration."""

from __future__ import annotations

from .constants import BORIC_ACID_G_PER_MOL


def boric_acid_concentration_g_l(
    sample_ml: float,
    titrant_ml: float,
    blank_ml: float,
    molarity: float,
    dilution_factor: float,
) -> float:
    """Return boric-acid concentration in grams per litre."""
    sample_ml = float(sample_ml)
    titrant_ml = float(titrant_ml)
    blank_ml = float(blank_ml)
    molarity = float(molarity)
    dilution_factor = float(dilution_factor)
    net_ml = max(0.0, titrant_ml - blank_ml)
    moles = 2.0 * net_ml / 1000.0 * molarity
    return moles * BORIC_ACID_G_PER_MOL / (sample_ml / 1000.0) * dilution_factor
