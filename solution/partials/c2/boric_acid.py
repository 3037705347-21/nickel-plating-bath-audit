"""Boric-acid concentration from a mannitol-assisted titration."""

from __future__ import annotations

import math

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
    values = (sample_ml, titrant_ml, blank_ml, molarity, dilution_factor)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("boric-acid titration values must be finite")
    if sample_ml <= 0 or molarity <= 0 or dilution_factor <= 0:
        raise ValueError(
            "sample volume, titrant molarity and dilution factor must be positive"
        )
    if blank_ml < 0 or titrant_ml < blank_ml:
        raise ValueError("blank volume must be between zero and titrant volume")
    net_ml = titrant_ml - blank_ml
    moles = net_ml / 1000.0 * molarity
    return moles * BORIC_ACID_G_PER_MOL / (sample_ml / 1000.0) * dilution_factor
