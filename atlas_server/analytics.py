"""Deterministic observations over the append-only world event stream."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def summarize_events(events: list[dict[str, Any]], *, after_sequence: int,
                     has_more: bool = False) -> dict[str, Any]:
    """Aggregate only observed event data; this layer makes no causal claims."""
    by_type: Counter[str] = Counter()
    by_actor: Counter[str] = Counter()
    by_day: dict[str, Counter[str]] = defaultdict(Counter)
    reeds_gathered = 0
    reeds_offered = 0
    damage_dealt = 0
    damage_received = 0
    victories = 0
    guard_actions = 0
    dodge_actions = 0
    conversations = 0
    first_meetings = 0
    beacons_awakened = 0

    for event in events:
        kind = event["type"]
        detail = event.get("detail") or {}
        by_type[kind] += 1
        by_actor[event["actor_id"]] += 1
        by_day[event["at"][:10]][kind] += 1
        if kind == "ResourceGathered":
            reeds_gathered += int(detail.get("quantity", 0))
        elif kind == "BeaconAwakened":
            reeds_offered += int((detail.get("offering") or {}).get("lumen_reed", 0))
            beacons_awakened += 1
        elif kind == "CreatureDamaged":
            damage_dealt += int(detail.get("damage", 0))
            damage_received += int(detail.get("player_damage", 0))
            victories += int(bool(detail.get("defeated")))
        elif kind == "PlayerGuarded":
            guard_actions += 1
        elif kind == "PlayerDodged":
            dodge_actions += 1
        elif kind == "NPCSpokenTo":
            conversations += 1
            first_meetings += int(bool(detail.get("first_meeting")))

    next_after = events[-1]["sequence"] if events else after_sequence
    return {
        "window": {"after_sequence": after_sequence, "through_sequence": next_after,
                   "event_count": len(events), "has_more": has_more},
        "activity": {"events_by_type": dict(sorted(by_type.items())),
                     "events_by_actor": dict(sorted(by_actor.items())),
                     "active_actor_count": len(by_actor)},
        "social": {"npc_conversations": conversations, "first_meetings": first_meetings},
        "progression": {"beacons_awakened": beacons_awakened},
        "resources": {"lumen_reeds_gathered": reeds_gathered,
                       "lumen_reeds_offered": reeds_offered,
                       "lumen_reed_net_flow": reeds_gathered - reeds_offered},
        "combat": {"attacks_resolved": by_type["CreatureDamaged"],
                   "damage_dealt": damage_dealt, "damage_received": damage_received,
                   "creatures_defeated": victories, "guards_raised": guard_actions,
                   "dodges_performed": dodge_actions},
        "timeline": [{"date": day, "events": dict(sorted(counts.items())),
                      "total": sum(counts.values())}
                     for day, counts in sorted(by_day.items())],
        "limitations": [
            "Metrics describe this event window and do not infer why behavior occurred.",
            "Retention is unavailable because the reference runtime has no durable account identity.",
        ],
    }
