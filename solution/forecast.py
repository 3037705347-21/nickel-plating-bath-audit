"""Forecast the bath composition needed before a production shift."""

from __future__ import annotations

import math

from .constants import FARADAY_C_PER_MOL, NICKEL_G_PER_MOL


def shift_start_targets_g_l(
    tank_volume_l: float,
    planned_charge_ah: float,
    cathode_efficiency: float,
    dragout_l: float,
    target_nickel_g_l: float,
    target_boric_acid_g_l: float,
    target_chloride_g_l: float,
) -> dict[str, object]:
    """Return deposition, drag-out losses, and pre-shift targets."""
    values = {
        "tank_volume_l": float(tank_volume_l),
        "planned_charge_ah": float(planned_charge_ah),
        "cathode_efficiency": float(cathode_efficiency),
        "dragout_l": float(dragout_l),
        "target_nickel_g_l": float(target_nickel_g_l),
        "target_boric_acid_g_l": float(target_boric_acid_g_l),
        "target_chloride_g_l": float(target_chloride_g_l),
    }
    if not all(math.isfinite(value) for value in values.values()):
        raise ValueError("shift forecast values must be finite")
    tank_volume_l = values["tank_volume_l"]
    planned_charge_ah = values["planned_charge_ah"]
    cathode_efficiency = values["cathode_efficiency"]
    dragout_l = values["dragout_l"]
    target_nickel_g_l = values["target_nickel_g_l"]
    target_boric_acid_g_l = values["target_boric_acid_g_l"]
    target_chloride_g_l = values["target_chloride_g_l"]
    if tank_volume_l <= 0:
        raise ValueError("tank volume must be positive")
    if planned_charge_ah < 0:
        raise ValueError("planned charge must not be negative")
    if not 0.0 <= cathode_efficiency <= 1.0:
        raise ValueError("cathode efficiency must be between zero and one")
    if dragout_l < 0 or dragout_l >= tank_volume_l:
        raise ValueError("drag-out volume must be non-negative and below tank volume")
    if min(target_nickel_g_l, target_boric_acid_g_l, target_chloride_g_l) <= 0:
        raise ValueError("end-of-shift targets must be positive")

    deposited_g = (
        planned_charge_ah
        * 3600.0
        * cathode_efficiency
        / (2.0 * FARADAY_C_PER_MOL)
        * NICKEL_G_PER_MOL
    )
    remaining_volume = tank_volume_l - dragout_l
    start = {
        "nickel": (target_nickel_g_l * tank_volume_l + deposited_g) / remaining_volume,
        "boric_acid": target_boric_acid_g_l * tank_volume_l / remaining_volume,
        "chloride": target_chloride_g_l * tank_volume_l / remaining_volume,
    }
    return {
        "nickel_deposited_g": deposited_g,
        "dragout_loss_g": {
            key: start[key] * dragout_l for key in ("nickel", "boric_acid", "chloride")
        },
        "shift_start_target_g_l": start,
    }
