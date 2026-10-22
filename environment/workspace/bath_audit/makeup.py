"""Makeup calculations for a nickel plating bath."""

from __future__ import annotations

from .constants import (
    BORIC_ACID_G_PER_MOL,
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
    tank_volume_l = float(tank_volume_l)
    nickel_g_l = float(nickel_g_l)
    boric_acid_g_l = float(boric_acid_g_l)
    chloride_g_l = float(chloride_g_l)
    target_nickel_g_l = float(target_nickel_g_l)
    target_boric_acid_g_l = float(target_boric_acid_g_l)
    target_chloride_g_l = float(target_chloride_g_l)
    nickel_sulfate_assay = float(nickel_sulfate_assay)
    nickel_chloride_assay = float(nickel_chloride_assay)
    boric_acid_assay = float(boric_acid_assay)

    nickel_need_g = max(0.0, target_nickel_g_l - nickel_g_l) * tank_volume_l
    boric_need_g = max(0.0, target_boric_acid_g_l - boric_acid_g_l) * tank_volume_l

    nickel_mol = nickel_need_g / NICKEL_G_PER_MOL
    sulfate_pure_g = nickel_mol * NICKEL_SULFATE_HEXAHYDRATE_G_PER_MOL
    boric_pure_g = boric_need_g

    additions = {
        "nickel_sulfate_hexahydrate": sulfate_pure_g / nickel_sulfate_assay / 1000.0,
        "nickel_chloride_hexahydrate": 0.0,
        "boric_acid": boric_pure_g / 1000.0,
    }
    return {
        "addition_kg": additions,
        "total_addition_kg": sum(additions.values()),
        "predicted_g_l": {
            "nickel": target_nickel_g_l,
            "boric_acid": target_boric_acid_g_l,
            "chloride": target_chloride_g_l,
        },
    }
