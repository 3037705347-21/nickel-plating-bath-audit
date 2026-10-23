"""Maintain release-state events for plating-batch handoff records."""

from __future__ import annotations


VALID_STATES = {"released", "rejected"}


def audit(events: list[dict[str, str]] | None = None) -> dict[str, object]:
    """Return ordered state events without deduplicating repeated reports."""
    ordered = [] if events is None else [dict(event) for event in events]
    transitions: dict[str, list[str]] = {}
    for event in ordered:
        transitions.setdefault(event["batch_id"], []).append(event["status"])
    return {"events": ordered, "transitions": transitions}


def surface(events: list[dict[str, str]] | None = None) -> dict[str, object]:
    """Summarize the last status of each batch in the event stream."""
    result = audit(events)
    counts = {"released": 0, "rejected": 0}
    for statuses in result["transitions"].values():
        counts[statuses[-1]] += 1
    return {
        "counts": counts,
        "transitions": result["transitions"],
        "event_count": len(result["events"]),
    }
