"""Build a plating-bath batch sheet from one CSV row."""

from __future__ import annotations

from .boric_acid import boric_acid_concentration_g_l
from .chloride import chloride_concentration_g_l
from .forecast import shift_start_targets_g_l
from .makeup import makeup_plan
from .nickel import nickel_concentration_g_l
from .packaging import package_plan


def audit_batch(row: dict[str, str]) -> dict[str, object]:
    """Convert one laboratory row into a structured makeup result."""
    tank_volume_l = float(row["tank_volume_l"])
    nickel = nickel_concentration_g_l(
        row["edta_sample_ml"],
        row["edta_titrant_ml"],
        row["edta_blank_ml"],
        row["edta_molarity"],
        row["dilution_factor"],
        row["copper_g_l"],
    )
    boric_acid = boric_acid_concentration_g_l(
        row["boric_sample_ml"],
        row["naoh_titrant_ml"],
        row["naoh_blank_ml"],
        row["naoh_molarity"],
        row["dilution_factor"],
    )
    chloride = chloride_concentration_g_l(
        row["chloride_sample_ml"],
        row["agno3_titrant_ml"],
        row["agno3_blank_ml"],
        row["agno3_molarity"],
        row["dilution_factor"],
    )
    target_nickel = float(row["target_nickel_g_l"])
    target_boric = float(row["target_boric_acid_g_l"])
    target_chloride = float(row["target_chloride_g_l"])
    forecast = shift_start_targets_g_l(
        tank_volume_l,
        row["planned_charge_ah"],
        row["cathode_efficiency"],
        row["dragout_l"],
        target_nickel,
        target_boric,
        target_chloride,
    )
    start_targets = forecast["shift_start_target_g_l"]
    exact_plan = makeup_plan(
        tank_volume_l,
        nickel,
        boric_acid,
        chloride,
        start_targets["nickel"],
        start_targets["boric_acid"],
        start_targets["chloride"],
        row["nickel_sulfate_assay"],
        row["nickel_chloride_assay"],
        row["boric_acid_assay"],
    )
    plan = package_plan(
        tank_volume_l,
        nickel,
        boric_acid,
        chloride,
        exact_plan,
        row["nickel_sulfate_assay"],
        row["nickel_chloride_assay"],
        row["boric_acid_assay"],
        row["nickel_sulfate_bag_kg"],
        row["nickel_chloride_bag_kg"],
        row["boric_acid_bag_kg"],
    )
    return {
        "batch_id": row["batch_id"],
        "tank_volume_l": tank_volume_l,
        "analysis_g_l": {
            "nickel": nickel,
            "boric_acid": boric_acid,
            "chloride": chloride,
        },
        "deficit_g": {
            "nickel": max(0.0, start_targets["nickel"] - nickel) * tank_volume_l,
            "boric_acid": max(0.0, start_targets["boric_acid"] - boric_acid)
            * tank_volume_l,
            "chloride": max(0.0, start_targets["chloride"] - chloride)
            * tank_volume_l,
        },
        "addition_kg": plan["addition_kg"],
        "bags": plan["bags"],
        "total_addition_kg": plan["total_addition_kg"],
        "predicted_g_l": plan["predicted_g_l"],
        "forecast": forecast,
    }
