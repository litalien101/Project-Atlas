"""Evidence-first explanations over authored world events.

This module summarizes recorded provenance. It does not infer causes or create
TruthRecords; those require a separate validated multi-source evidence workflow.
"""

from __future__ import annotations

from typing import Any


def explain_event_provenance(record: dict[str, Any]) -> dict[str, Any]:
    event = record.get("event")
    if not isinstance(event, dict) or not event.get("event_id") or not event.get("rationale"):
        raise ValueError("The requested world event has no valid provenance record.")
    return {
        "kind": "authored_event_provenance",
        "event": event,
        "entities": record.get("entities", []),
        "relationships": record.get("relationships", []),
        "evidence": [{
            "id": event["event_id"],
            "kind": "immutable_world_event",
            "source": event["source"],
            "recorded_at": event["at"],
            "actor_id": event["actor_id"],
            "rationale": event["rationale"],
            "recorded_result": event.get("detail", {}),
        }],
        "confidence": None,
        "confidence_status": "not_applicable_to_authored_provenance",
        "truth_record_created": False,
        "limitations": [
            "This trace reports what the event author recorded; it does not infer a root cause.",
            "Derived claims require at least two distinct evidence references and confidence >= 0.80.",
        ],
    }
