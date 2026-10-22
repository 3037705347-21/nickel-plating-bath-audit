"""Return malformed JSON while exiting successfully."""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Write a truncated JSON fragment."""
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 2:
        return 2
    Path(arguments[1]).write_text('{"batch_id": "Ni-2026-1018-A",\n', encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
