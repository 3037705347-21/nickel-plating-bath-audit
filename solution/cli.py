"""Command-line entry point for plating-bath batch sheets."""

from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
from pathlib import Path

from .audit import audit_batch


COLUMNS = (
    "batch_id",
    "tank_volume_l",
    "edta_sample_ml",
    "edta_titrant_ml",
    "edta_blank_ml",
    "edta_molarity",
    "boric_sample_ml",
    "naoh_titrant_ml",
    "naoh_blank_ml",
    "naoh_molarity",
    "chloride_sample_ml",
    "agno3_titrant_ml",
    "agno3_blank_ml",
    "agno3_molarity",
    "target_nickel_g_l",
    "target_boric_acid_g_l",
    "target_chloride_g_l",
    "nickel_sulfate_assay",
    "nickel_chloride_assay",
    "boric_acid_assay",
    "dilution_factor",
    "copper_g_l",
    "planned_charge_ah",
    "cathode_efficiency",
    "dragout_l",
    "nickel_sulfate_bag_kg",
    "nickel_chloride_bag_kg",
    "boric_acid_bag_kg",
)


def _read_record(path: str) -> dict[str, str]:
    """Read exactly one laboratory record and check its columns by name."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError("missing header")
        if len(fieldnames) != len(set(fieldnames)):
            raise ValueError("duplicate columns")
        if set(fieldnames) != set(COLUMNS):
            raise ValueError("unexpected columns")
        rows = list(reader)
    if len(rows) != 1:
        raise ValueError("record must contain exactly one data row")
    row = rows[0]
    if not row["batch_id"].strip():
        raise ValueError("batch_id must not be empty")
    return row


def run(record_path: str, output_path: str) -> None:
    """Create a batch-sheet JSON file without exposing a partial file."""
    row = _read_record(record_path)
    report = audit_batch(row)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface."""
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 2:
        print("usage: python -m bath_audit.cli RECORD.csv BATCH.json", file=sys.stderr)
        return 2
    try:
        run(*arguments)
    except (OSError, ValueError, KeyError, ZeroDivisionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
