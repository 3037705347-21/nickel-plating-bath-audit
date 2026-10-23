# Behavior evidence

This directory records the current-version traceability and isolated mutation
evidence for the nickel plating bath task.

- `coverage-matrix.json`: 29 atomic behaviors, each mapped to a test, fixture,
  case ID, direct assertion and counterexample. The matrix also records the
  exact instruction and test hashes.
- `oracle-stdout.txt`: direct execution evidence for all 27 registered test
  functions; the two extra case IDs are additional boundary behaviors mapped to
  the same tests.
- `nop-stdout.txt`: baseline execution with the initial implementation.
- `mutation-evidence.jsonl`: one applicable unified-diff mutation per behavior,
  with the mutated file hash, operator, nonzero pytest exit and output file.
- `mutation-outputs/*.log`: raw failing output for each isolated mutation.

Rebuild the evidence from the task directory with:

```bash
python3 solution/build_behavior_evidence.py
```

The evidence builder uses the fixed environment image, runs each test function
against the complete solution and the initial baseline, applies each mutation
to a temporary container copy, and records only actual command results.
