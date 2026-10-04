"""Translate a deliberately small, explicit prompt vocabulary into profile fields.

This compiler never guesses numeric anatomy from qualitative adjectives. It
preserves the entire request and reports which values it did and did not map.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from character_design_profile import SCHEMA_PATH, validate_profile

ROOT = Path(__file__).resolve().parents[2]
STARTER_PROFILE = ROOT / "art/characters/profiles/starter_humanoid.json"

CONTROL_ALIASES: dict[str, tuple[str, ...]] = {
    "build_percent": ("body build", "build", "bulk"),
    "shoulder_percent": ("shoulder width", "shoulders", "shoulder"),
    "arm_length_percent": ("arm length", "arms"),
    "leg_length_percent": ("leg length", "legs"),
    "head_percent": ("head size", "head"),
    "torso_length_percent": ("torso length", "torso"),
    "bust_percent": ("chest", "bust"),
    "stomach_percent": ("stomach", "belly"),
    "hips_percent": ("hips", "hip width"),
    "glutes_percent": ("glutes", "glute size"),
    "thighs_percent": ("thigh size", "thighs", "thigh"),
    "jaw_percent": ("jaw size", "jaw"),
    "hand_percent": ("hand size", "hands", "hand"),
    "foot_percent": ("foot size", "feet", "foot"),
    "ear_percent": ("ear size", "ears", "ear"),
    "muscle_percent": ("muscle definition", "muscularity", "muscle"),
    "nose_percent": ("nose size", "nose"),
}


def _profile_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _explicit_percent_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias).replace(r"\ ", r"\s+")
    return re.compile(
        rf"(?<![\w]){escaped}\s*(?:(?:is|to|at)\s*)?(?::|=)?\s*"
        rf"(?P<value>\d+(?:\.\d+)?)\s*%",
        re.IGNORECASE,
    )


def _apply_control(prompt: str, profile: dict[str, Any], key: str) -> list[dict[str, Any]]:
    property_schema = _profile_schema()["properties"]["body"]["properties"][key]
    matches: list[tuple[int, re.Match[str], str]] = []
    for alias in CONTROL_ALIASES[key]:
        matches.extend((m.start(), m, alias) for m in _explicit_percent_pattern(alias).finditer(prompt))
    matches.sort(key=lambda item: item[0])
    results = []
    for _, match, alias in matches:
        number = float(match.group("value"))
        value = int(round(number))
        low, high = property_schema["minimum"], property_schema["maximum"]
        if not low <= value <= high:
            results.append({
                "field": key,
                "value": value,
                "status": "needs_revision",
                "source_text": match.group(0),
                "message": f"Use a value from {low}% to {high}%.",
            })
            continue
        previous = profile["body"][key]
        profile["body"][key] = value
        results.append({
            "field": key,
            "value": value,
            "previous_value": previous,
            "status": "applied",
            "source_text": match.group(0),
            "message": f"Set {key.removesuffix('_percent').replace('_', ' ')} to {value}%.",
        })
    return results


def _apply_height(prompt: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"(?<![\w])(?:"
        r"(?:height|tall)\s*(?:(?:is|to|of)\s*)?(?::|=)?\s*"
        r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>cm|m|meters?|metres?)"
        r"|(?P<value_before>\d+(?:\.\d+)?)\s*(?P<unit_before>cm|m|meters?|metres?)\s*(?:tall|high)"
        r")\b",
        re.IGNORECASE,
    )
    results = []
    for match in pattern.finditer(prompt):
        amount = float(match.group("value") or match.group("value_before"))
        unit = (match.group("unit") or match.group("unit_before")).lower()
        centimeters = amount * (100 if unit == "m" or unit.startswith(("meter", "metre")) else 1)
        value = int(round(centimeters))
        low = _profile_schema()["properties"]["body"]["properties"]["height_cm"]["minimum"]
        high = _profile_schema()["properties"]["body"]["properties"]["height_cm"]["maximum"]
        if not low <= value <= high:
            results.append({
                "field": "height_cm",
                "value": value,
                "status": "needs_revision",
                "source_text": match.group(0),
                "message": f"Use a height from {low} cm to {high} cm.",
            })
            continue
        previous = profile["body"]["height_cm"]
        profile["body"]["height_cm"] = value
        results.append({
            "field": "height_cm",
            "value": value,
            "previous_value": previous,
            "status": "applied",
            "source_text": match.group(0),
            "message": f"Set height to {value} cm.",
        })
    return results


def compile_text(prompt: str) -> dict[str, Any]:
    """Return a validated profile draft plus explicit scope and parse evidence."""
    text = prompt.strip()
    if not text:
        raise ValueError("Enter a character description first.")
    if len(text) > 2000:
        raise ValueError("Keep the description to 2,000 characters or fewer.")
    source = json.loads(STARTER_PROFILE.read_text(encoding="utf-8"))
    profile = copy.deepcopy(validate_profile(source))
    profile["concept"]["source_prompt"] = text
    original_profile = copy.deepcopy(profile)

    controls: list[dict[str, Any]] = []
    controls.extend(_apply_height(text, profile))
    for field in CONTROL_ALIASES:
        controls.extend(_apply_control(text, profile, field))

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in controls:
        if item["status"] == "applied":
            grouped.setdefault(item["field"], []).append(item)
    conflicts = []
    for field, items in grouped.items():
        values = {item["value"] for item in items}
        if len(values) < 2:
            continue
        profile["body"][field] = original_profile["body"][field]
        for item in items:
            item["status"] = "conflict"
        conflicts.append({
            "kind": "conflicting_values",
            "source_text": ", ".join(item["source_text"] for item in items),
            "message": f"The brief gives conflicting values for {field.replace('_', ' ')}. Keep one value and resubmit.",
        })

    blocking = []
    invalid = [item for item in controls if item["status"] == "needs_revision"]
    blocking.extend(conflicts)
    blocking.extend({
        "kind": "out_of_range",
        "source_text": item["source_text"],
        "message": item["message"],
    } for item in invalid)
    applied = [item for item in controls if item["status"] == "applied"]

    # Kept separate from parsed geometry values: these requests are retained
    # for later authoring, but the geometry builder does not act on them.
    later_stage_terms = [
        "texture", "surface detail", "scar", "scars", "eye color",
        "material", "color", "walk", "run", "jump", "climb", "animation", "idle",
    ]
    later_stage = [term for term in later_stage_terms if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE)]
    return {
        "compiler": "atlas-deterministic-character-text-compiler/v1",
        "profile": profile,
        "parsed_fields": applied,
        "needs_revision": invalid,
        "blocking_questions": blocking,
        "later_stage_mentions": later_stage,
        "source_text_preserved": True,
        "scope_notice": (
            "Only explicit supported measurements and feature toggles change geometry. "
            "Qualitative wording is preserved as source text and is not guessed into mesh controls."
        ),
        "ready_for_plan": not blocking,
    }
