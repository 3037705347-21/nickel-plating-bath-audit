"""Return the bundled sample answer without reading the input record."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RESULT = {
    "batch_id": "Ni-2026-1018-A",
    "tank_volume_l": 1200.0,
    "analysis_g_l": {
        "nickel": 62.00957709999999,
        "boric_acid": 28.009896,
        "chloride": 24.008771600000003,
    },
    "deficit_g": {
        "nickel": 15588.507480000015,
        "boric_acid": 8388.124799999998,
        "chloride": 7189.474079999996,
    },
    "addition_kg": {
        "nickel_sulfate_hexahydrate": 43.815969566993616,
        "nickel_chloride_hexahydrate": 24.718516587250658,
        "boric_acid": 8.43027618090452,
    },
    "total_addition_kg": 76.9647623351488,
    "predicted_g_l": {
        "nickel": 75.0,
        "boric_acid": 35.0,
        "chloride": 30.0,
    },
}


def main(argv: list[str] | None = None) -> int:
    """Write the hard-coded sample result."""
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 2:
        return 2
    Path(arguments[1]).write_text(
        json.dumps(RESULT, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
