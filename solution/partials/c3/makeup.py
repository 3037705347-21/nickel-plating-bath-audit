"""Makeup calculations for a nickel plating bath."""

from __future__ import annotations

import math

from .constants import (
    CHLORIDE_G_PER_MOL,
    NICKEL_CHLORIDE_HEXAHYDRATE_G_PER_MOL,
    NICKEL_G_PER_MOL,
    NICKEL_SULFATE_HEXAHYDRATE_G_PER_MOL,
)


def makeup_plan(
    tank_volume_l: float,
    nickel_g_l: float,
    boric_acid_g_l: float,
    chloride_g_l: float,
    target_nickel_g_l: float,
    target_boric_acid_g_l: float,
    target_chloride_g_l: float,
    nickel_sulfate_assay: float,
    nickel_chloride_assay: float,
    boric_acid_assay: float,
) -> dict[str, object]:
    """Return commercial-material additions and predicted bath concentrations."""
    values = {
        "tank_volume_l": float(tank_volume_l),
        "nickel_g_l": float(nickel_g_l),
        "boric_acid_g_l": float(boric_acid_g_l),
        "chloride_g_l": float(chloride_g_l),
        "target_nickel_g_l": float(target_nickel_g_l),
        "target_boric_acid_g_l": float(target_boric_acid_g_l),
        "target_chloride_g_l": float(target_chloride_g_l),
        "nickel_sulfate_assay": float(nickel_sulfate_assay),
        "nickel_chloride_assay": float(nickel_chloride_assay),
        "boric_acid_assay": float(boric_acid_assay),
    }
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError("makeup values must be finite")
    tank_volume_l = values["tank_volume_l"]
    nickel_g_l = values["nickel_g_l"]
    boric_acid_g_l = values["boric_acid_g_l"]
    chloride_g_l = values["chloride_g_l"]
    target_nickel_g_l = values["target_nickel_g_l"]
    target_boric_acid_g_l = values["target_boric_acid_g_l"]
    target_chloride_g_l = values["target_chloride_g_l"]
    nickel_sulfate_assay = values["nickel_sulfate_assay"]
    nickel_chloride_assay = values["nickel_chloride_assay"]
    boric_acid_assay = values["boric_acid_assay"]

    if tank_volume_l <= 0:
        raise ValueError("tank volume must be positive")
    if min(nickel_g_l, boric_acid_g_l, chloride_g_l) < 0:
        raise ValueError("measured concentrations must not be negative")
    if min(target_nickel_g_l, target_boric_acid_g_l, target_chloride_g_l) <= 0:
        raise ValueError("target concentrations must be positive")
    for assay in (nickel_sulfate_assay, nickel_chloride_assay, boric_acid_assay):
        if not 0.0 < assay <= 1.0:
            raise ValueError("material assays must be between zero and one")

    nickel_need_g = max(0.0, target_nickel_g_l - nickel_g_l) * tank_volume_l
    boric_need_g = max(0.0, target_boric_acid_g_l - boric_acid_g_l) * tank_volume_l
    chloride_need_g = max(0.0, target_chloride_g_l - chloride_g_l) * tank_volume_l

    nickel_need_mol = nickel_need_g / NICKEL_G_PER_MOL
    chloride_need_mol = chloride_need_g / CHLORIDE_G_PER_MOL
    nickel_chloride_mol = chloride_need_mol / 2.0
    nickel_sulfate_mol = nickel_need_mol - nickel_chloride_mol
    if nickel_sulfate_mol < -1e-12:
        raise ValueError(
            "chloride demand exceeds the chloride supplied by the available nickel deficit"
        )
    nickel_sulfate_mol = max(0.0, nickel_sulfate_mol)

    sulfate_pure_g = nickel_sulfate_mol * NICKEL_SULFATE_HEXAHYDRATE_G_PER_MOL
    chloride_pure_g = nickel_chloride_mol * NICKEL_CHLORIDE_HEXAHYDRATE_G_PER_MOL
    boric_pure_g = boric_need_g
    additions = {
        "nickel_sulfate_hexahydrate": sulfate_pure_g / nickel_sulfate_assay / 1000.0,
        "nickel_chloride_hexahydrate": chloride_pure_g / nickel_chloride_assay / 1000.0,
        "boric_acid": boric_pure_g / boric_acid_assay / 1000.0,
    }
    predicted_nickel = nickel_g_l + (nickel_sulfate_mol + nickel_chloride_mol) * (
        NICKEL_G_PER_MOL / tank_volume_l
    )
    predicted_boric = boric_acid_g_l + boric_pure_g / tank_volume_l
    predicted_chloride = chloride_g_l + 2.0 * nickel_chloride_mol * (
        CHLORIDE_G_PER_MOL / tank_volume_l
    )
    return {
        "addition_kg": additions,
        "total_addition_kg": sum(additions.values()),
        "predicted_g_l": {
            "nickel": predicted_nickel,
            "boric_acid": predicted_boric,
            "chloride": predicted_chloride,
        },
    }
