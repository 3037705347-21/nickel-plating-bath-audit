"""Convert a theoretical makeup plan into full-bag warehouse additions."""

from __future__ import annotations

import math

from .constants import (
    CHLORIDE_G_PER_MOL,
    NICKEL_CHLORIDE_HEXAHYDRATE_G_PER_MOL,
    NICKEL_G_PER_MOL,
    NICKEL_SULFATE_HEXAHYDRATE_G_PER_MOL,
)


def _whole_bags(required_kg: float, bag_kg: float) -> int:
    """Round a required commercial mass up to complete bags."""
    ratio = required_kg / bag_kg
    nearest = round(ratio)
    if math.isclose(ratio, nearest, rel_tol=0.0, abs_tol=4.0 * math.ulp(max(1.0, ratio))):
        return int(nearest)
    return math.ceil(ratio)


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
    """Return full-bag additions and concentrations from the packaged mass."""
    values = (
        tank_volume_l,
        nickel_g_l,
        boric_acid_g_l,
        chloride_g_l,
        nickel_sulfate_assay,
        nickel_chloride_assay,
        boric_acid_assay,
        nickel_sulfate_bag_kg,
        nickel_chloride_bag_kg,
        boric_acid_bag_kg,
    )
    numbers = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in numbers):
        raise ValueError("packaging values must be finite")
    (
        tank_volume_l,
        nickel_g_l,
        boric_acid_g_l,
        chloride_g_l,
        nickel_sulfate_assay,
        nickel_chloride_assay,
        boric_acid_assay,
        nickel_sulfate_bag_kg,
        nickel_chloride_bag_kg,
        boric_acid_bag_kg,
    ) = numbers
    if tank_volume_l <= 0:
        raise ValueError("tank volume must be positive")
    if min(nickel_g_l, boric_acid_g_l, chloride_g_l) < 0:
        raise ValueError("current concentrations must not be negative")
    for assay in (nickel_sulfate_assay, nickel_chloride_assay, boric_acid_assay):
        if not 0.0 < assay <= 1.0:
            raise ValueError("assays must be greater than zero and at most one")
    for bag_kg in (nickel_sulfate_bag_kg, nickel_chloride_bag_kg, boric_acid_bag_kg):
        if bag_kg <= 0:
            raise ValueError("bag sizes must be positive")

    required = exact_plan["addition_kg"]
    bag_sizes = {
        "nickel_sulfate_hexahydrate": nickel_sulfate_bag_kg,
        "nickel_chloride_hexahydrate": nickel_chloride_bag_kg,
        "boric_acid": boric_acid_bag_kg,
    }
    bags = {key: _whole_bags(float(required[key]), bag_sizes[key]) for key in bag_sizes}
    additions = {key: bags[key] * bag_sizes[key] for key in bag_sizes}
    sulfate_pure_g = (
        additions["nickel_sulfate_hexahydrate"] * 1000.0 * nickel_sulfate_assay
    )
    chloride_pure_g = (
        additions["nickel_chloride_hexahydrate"] * 1000.0 * nickel_chloride_assay
    )
    boric_pure_g = additions["boric_acid"] * 1000.0 * boric_acid_assay
    sulfate_mol = sulfate_pure_g / NICKEL_SULFATE_HEXAHYDRATE_G_PER_MOL
    chloride_mol = chloride_pure_g / NICKEL_CHLORIDE_HEXAHYDRATE_G_PER_MOL
    return {
        "addition_kg": additions,
        "bags": bags,
        "total_addition_kg": sum(additions.values()),
        "predicted_g_l": {
            "nickel": nickel_g_l
            + (sulfate_mol + chloride_mol) * NICKEL_G_PER_MOL / tank_volume_l,
            "boric_acid": boric_acid_g_l + boric_pure_g / tank_volume_l,
            "chloride": chloride_g_l
            + 2.0 * chloride_mol * CHLORIDE_G_PER_MOL / tank_volume_l,
        },
    }
