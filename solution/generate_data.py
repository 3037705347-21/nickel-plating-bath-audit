#!/usr/bin/env python3
"""Generate the bundled simulated laboratory record."""

from __future__ import annotations

import csv
import random
from pathlib import Path

NICKEL_G_PER_MOL = 58.6934
BORIC_ACID_G_PER_MOL = 61.832
CHLORIDE_G_PER_MOL = 35.453


def main() -> None:
    """Write one reproducible simulated titration record."""
    rng = random.Random(20261022)
    tank_volume_l = 1200.0
    nickel_g_l = 62.0
    boric_acid_g_l = 28.0
    chloride_g_l = 24.0

    edta_sample_ml = 2.0
    boric_sample_ml = 5.0
    chloride_sample_ml = 5.0
    edta_blank_ml = 0.32
    naoh_blank_ml = 0.25
    agno3_blank_ml = 0.12
    molarity = 0.1

    edta_exact = nickel_g_l * edta_sample_ml / 1000.0 / NICKEL_G_PER_MOL / molarity * 1000.0
    naoh_exact = boric_acid_g_l * boric_sample_ml / 1000.0 / BORIC_ACID_G_PER_MOL / molarity * 1000.0
    agno3_exact = chloride_g_l * chloride_sample_ml / 1000.0 / CHLORIDE_G_PER_MOL / molarity * 1000.0

    record = {
        "batch_id": "Ni-2026-1018-A",
        "tank_volume_l": f"{tank_volume_l:.1f}",
        "edta_sample_ml": f"{edta_sample_ml:.1f}",
        "edta_titrant_ml": f"{edta_blank_ml + edta_exact + rng.uniform(-0.02, 0.02):.2f}",
        "edta_blank_ml": f"{edta_blank_ml:.2f}",
        "edta_molarity": f"{molarity:.4f}",
        "boric_sample_ml": f"{boric_sample_ml:.1f}",
        "naoh_titrant_ml": f"{naoh_blank_ml + naoh_exact + rng.uniform(-0.02, 0.02):.2f}",
        "naoh_blank_ml": f"{naoh_blank_ml:.2f}",
        "naoh_molarity": f"{molarity:.4f}",
        "chloride_sample_ml": f"{chloride_sample_ml:.1f}",
        "agno3_titrant_ml": f"{agno3_blank_ml + agno3_exact + rng.uniform(-0.02, 0.02):.2f}",
        "agno3_blank_ml": f"{agno3_blank_ml:.2f}",
        "agno3_molarity": f"{molarity:.4f}",
        "target_nickel_g_l": "75.0",
        "target_boric_acid_g_l": "35.0",
        "target_chloride_g_l": "30.0",
        "nickel_sulfate_assay": "0.985",
        "nickel_chloride_assay": "0.975",
        "boric_acid_assay": "0.995",
        "dilution_factor": "1.0",
        "copper_g_l": "0.12",
        "planned_charge_ah": "1800.0",
        "cathode_efficiency": "0.94",
        "dragout_l": "15.0",
        "nickel_sulfate_bag_kg": "25.0",
        "nickel_chloride_bag_kg": "10.0",
        "boric_acid_bag_kg": "5.0",
    }
    destination = (
        Path(__file__).resolve().parent.parent
        / "environment"
        / "workspace"
        / "data"
        / "lab_record.csv"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(record))
        writer.writeheader()
        writer.writerow(record)


if __name__ == "__main__":
    main()
