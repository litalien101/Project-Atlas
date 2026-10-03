"""Validation for the persisted Atlas female-base appearance profile v1."""

from __future__ import annotations

import re
from typing import Any


DEFAULT_APPEARANCE: dict[str, Any] = {
    "schema": "atlas-character-profile/v1",
    "height_cm": 168,
    "weight_kg": 70,
    "skin_tone": "#b17c5e",
    "bust_percent": 100,
    "stomach_percent": 100,
    "hips_percent": 100,
    "glutes_percent": 100,
    "thighs_percent": 100,
    "underwear_top": False,
    "underwear_bottom": False,
    "shoulder_guards": False,
}

INTEGER_RANGES = {
    "height_cm": (150, 190),
    "weight_kg": (45, 120),
    "bust_percent": (70, 130),
    "stomach_percent": (70, 140),
    "hips_percent": (80, 125),
    "glutes_percent": (70, 130),
    "thighs_percent": (80, 125),
}
BOOLEAN_FIELDS = {"underwear_top", "underwear_bottom", "shoulder_guards"}
PROFILE_FIELDS = set(DEFAULT_APPEARANCE)


def validate_appearance(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Character appearance must be an object.")
    if set(value) != PROFILE_FIELDS:
        missing = sorted(PROFILE_FIELDS - set(value))
        extra = sorted(set(value) - PROFILE_FIELDS)
        details = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if extra:
            details.append(f"unsupported fields: {', '.join(extra)}")
        raise ValueError("Character appearance fields are invalid (" + "; ".join(details) + ").")
    if value["schema"] != DEFAULT_APPEARANCE["schema"]:
        raise ValueError("Unsupported character appearance schema.")

    profile = {"schema": DEFAULT_APPEARANCE["schema"]}
    for field, (minimum, maximum) in INTEGER_RANGES.items():
        item = value[field]
        if isinstance(item, bool) or not isinstance(item, int) or not minimum <= item <= maximum:
            raise ValueError(f"{field} must be a whole number from {minimum} to {maximum}.")
        profile[field] = item
    tone = value["skin_tone"]
    if not isinstance(tone, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", tone) is None:
        raise ValueError("skin_tone must be a six-digit hexadecimal color.")
    profile["skin_tone"] = tone.lower()
    for field in BOOLEAN_FIELDS:
        if not isinstance(value[field], bool):
            raise ValueError(f"{field} must be a boolean.")
        profile[field] = value[field]
    return profile
