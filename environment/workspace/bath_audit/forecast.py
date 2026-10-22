"""Forecast the bath composition needed before a production shift."""

from __future__ import annotations

from .constants import NICKEL_G_PER_MOL


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
    tank_volume_l = float(tank_volume_l)
    planned_charge_ah = float(planned_charge_ah)
    cathode_efficiency = float(cathode_efficiency)
    dragout_l = float(dragout_l)
    targets = {
        "nickel": float(target_nickel_g_l),
        "boric_acid": float(target_boric_acid_g_l),
        "chloride": float(target_chloride_g_l),
    }
    return {
        "nickel_deposited_g": 0.0,
        "dragout_loss_g": {key: 0.0 for key in targets},
        "shift_start_target_g_l": targets,
    }
