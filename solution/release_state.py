"""Maintain release-state events for plating-batch handoff records."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

VALID_STATES = {"released", "rejected"}
STATE_VERSION = 1


def _validated_events(events: list[dict[str, str]] | None) -> list[dict[str, str]]:
    """Return copied, validated events."""
    ordered = []
    for event in [] if events is None else events:
        event_id = event.get("event_id")
        batch_id = event.get("batch_id")
        status = event.get("status")
        if not event_id or not batch_id or status not in VALID_STATES:
            raise ValueError("event_id, batch_id, and status are required")
        ordered.append(dict(event))
    return ordered


def _deduplicated(events: list[dict[str, str]]) -> list[dict[str, str]]:
    """Drop later reports that reuse an event identifier."""
    ordered = []
    seen: set[str] = set()
    for event in events:
        event_id = event["event_id"]
        if event_id in seen:
            continue
        seen.add(event_id)
        ordered.append(event)
    return ordered


def _load_state(state_path: str | os.PathLike[str] | None) -> list[dict[str, str]]:
    """Load and validate an ordered event journal."""
    if state_path is None:
        return []
    path = Path(state_path)
    if not path.exists():
        return []
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("state file is not valid JSON") from exc
    if (
        not isinstance(state, dict)
        or state.get("version") != STATE_VERSION
        or not isinstance(state.get("events"), list)
    ):
        raise ValueError("state file has an unsupported structure")
    return _deduplicated(_validated_events(state["events"]))


def _write_state(
    state_path: str | os.PathLike[str],
    events: list[dict[str, str]],
) -> None:
    """Atomically replace the persisted event journal."""
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(
                {"version": STATE_VERSION, "events": events},
                handle,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
            )
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def audit(
    events: list[dict[str, str]] | None = None,
    state_path: str | os.PathLike[str] | None = None,
) -> dict[str, object]:
    """Merge state events across calls with event-id deduplication."""
    existing = _load_state(state_path)
    incoming = _validated_events(events)
    merged = _deduplicated(existing + incoming)
    if state_path is not None and len(merged) != len(existing):
        _write_state(state_path, merged)
    transitions: dict[str, list[str]] = {}
    for event in merged:
        transitions.setdefault(event["batch_id"], []).append(event["status"])
    return {"events": merged, "transitions": transitions}


def surface(
    events: list[dict[str, str]] | None = None,
    state_path: str | os.PathLike[str] | None = None,
) -> dict[str, object]:
    """Summarize the persisted last status of each batch."""
    result = audit(events, state_path=state_path)
    counts = {"released": 0, "rejected": 0}
    for statuses in result["transitions"].values():
        counts[statuses[-1]] += 1
    return {
        "counts": counts,
        "transitions": result["transitions"],
        "event_count": len(result["events"]),
    }
