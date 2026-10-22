# Nickel bath batch sheet

The `bath_audit` package converts one laboratory titration record into a
nickel plating bath makeup sheet.

```bash
python -m bath_audit.cli data/lab_record.csv batch.json
```

`data/lab_record.csv` is a reproducible simulated record for checking the
command and report shape. It is not a laboratory record.

The package exposes separate nickel, boric-acid, chloride, shift-forecast,
makeup, and full-bag packaging calculations so the plating line's calibration
notebooks can call the same code without going through the CSV command.
