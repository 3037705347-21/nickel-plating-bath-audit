"""Convert a theoretical makeup plan into full-bag warehouse additions."""

from __future__ import annotations


def package_plan(
    tank_volume_l: float,
    nickel_g_l: float,
    boric_acid_g_l: float,
    chloride_g_l: float,
    exact_plan: dict[str, object],
    nickel_sulfate_assay: float,
    nickel_chloride_assay: float,
    boric_acid_assay: float,
    nickel_sulfate_bag_kg: float,
    nickel_chloride_bag_kg: float,
    boric_acid_bag_kg: float,
) -> dict[str, object]:
    """Return packaged additions without changing the exact plan."""
    additions = exact_plan["addition_kg"]
    return {
        "addition_kg": additions,
        "bags": {
            "nickel_sulfate_hexahydrate": 0,
            "nickel_chloride_hexahydrate": 0,
            "boric_acid": 0,
        },
        "total_addition_kg": exact_plan["total_addition_kg"],
        "predicted_g_l": exact_plan["predicted_g_l"],
    }
