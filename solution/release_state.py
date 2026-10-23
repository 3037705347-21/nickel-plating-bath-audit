"""Maintain release-state events for plating-batch handoff records."""

from __future__ import annotations


VALID_STATES = {"released", "rejected"}


def audit(events: list[dict[str, str]] | None = None) -> dict[str, object]:
    """Return ordered state events with event-id deduplication."""
    ordered: list[dict[str, str]] = []
    seen: set[str] = set()
    for event in [] if events is None else events:
        event_id = event.get("event_id")
        status = event.get("status")
        if not event_id or status not in VALID_STATES:
            raise ValueError("event_id and status are required")
        if event_id in seen:
            continue
        seen.add(event_id)
        ordered.append(dict(event))
    transitions: dict[str, list[str]] = {}
    for event in ordered:
        transitions.setdefault(event["batch_id"], []).append(event["status"])
    return {"events": ordered, "transitions": transitions}


def surface(events: list[dict[str, str]] | None = None) -> dict[str, object]:
    """Summarize the last status of each batch after event deduplication."""
    result = audit(events)
    counts = {"released": 0, "rejected": 0}
    for statuses in result["transitions"].values():
        counts[statuses[-1]] += 1
    return {
        "counts": counts,
        "transitions": result["transitions"],
        "event_count": len(result["events"]),
    }
