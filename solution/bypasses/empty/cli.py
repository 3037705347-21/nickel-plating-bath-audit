"""Return an empty JSON object while ignoring the record."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Write an empty result and exit successfully."""
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 2:
        return 2
    Path(arguments[1]).write_text(json.dumps({}) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
