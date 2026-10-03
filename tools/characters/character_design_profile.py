"""Shared validation for AI-authored Atlas design profiles."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "specs/atlas-character-design-profile-v1.schema.json"
PROFILE_SCHEMA = "atlas-character-design-profile/v1"
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
SLUG = re.compile(r"^[a-z][a-z0-9_]{1,47}$")
RANGES = {
    "height_cm": (145, 260), "build_percent": (70, 150),
    "shoulder_percent": (75, 150), "arm_length_percent": (75, 130),
    "leg_length_percent": (75, 130), "head_percent": (75, 160),
    "torso_length_percent": (80, 125),
    "bust_percent": (70, 130), "stomach_percent": (70, 140),
    "hips_percent": (80, 125), "glutes_percent": (70, 130),
    "thighs_percent": (80, 125),
    "jaw_percent": (75, 150), "hand_percent": (75, 150),
    "foot_percent": (75, 150), "ear_percent": (75, 175),
    "muscle_percent": (65, 160),
    "nose_percent": (70, 160),
}
ARCHETYPES = {"humanoid", "troll", "orc", "elf", "goblin"}
STYLES = {"realistic", "stylized", "low_poly", "painted"}
ACTIONS = {"idle", "walk", "run", "jump", "fall", "land", "climb", "swim", "attack"}
PALETTE_KEYS = {"skin", "secondary", "accent", "eyes", "horns", "tusks"}
TRAIT_KEYS = {"horns", "tusks", "pointed_ears"}


def _object(value: Any, expected: set[str], label: str, optional: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object.")
    allowed = expected | (optional or set())
    missing, extra = expected - set(value), set(value) - allowed
    if missing or extra:
        details = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if extra:
            details.append("unsupported " + ", ".join(sorted(extra)))
        raise ValueError(f"{label} has invalid fields ({'; '.join(details)}).")
    return value


def validate_profile(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("profile must be an object.")
    value = dict(value)
    value.setdefault("style", "realistic")
    top = _object(value, {"schema", "character_id", "display_name", "concept", "base_template", "style", "body", "palette", "traits", "actions"}, "profile", {"reference_calibration"})
    if top["schema"] != PROFILE_SCHEMA:
        raise ValueError(f"schema must be {PROFILE_SCHEMA!r}.")
    if not isinstance(top["character_id"], str) or not SLUG.fullmatch(top["character_id"]):
        raise ValueError("character_id must be a lowercase slug (letters, digits, underscores).")
    if not isinstance(top["display_name"], str) or not top["display_name"].strip() or len(top["display_name"]) > 80:
        raise ValueError("display_name must contain 1 to 80 characters.")
    if top["base_template"] != "atlas_parametric_humanoid_v1":
        raise ValueError("v1 generation supports only the atlas_parametric_humanoid_v1 template.")
    if not isinstance(top["style"], str) or top["style"] not in STYLES:
        raise ValueError(f"style must be one of: {', '.join(sorted(STYLES))}.")

    if "reference_calibration" in top:
        calibration = _object(
            top["reference_calibration"],
            {"record", "source_path", "source_sha256", "license", "use", "measurements"},
            "reference_calibration", {"geometry_seed_review"},
        )
        if not isinstance(calibration["record"], str) or not calibration["record"].strip() or len(calibration["record"]) > 240:
            raise ValueError("reference_calibration.record must be a non-empty path or identifier up to 240 characters.")
        if not isinstance(calibration["source_path"], str) or not calibration["source_path"].strip() or len(calibration["source_path"]) > 500:
            raise ValueError("reference_calibration.source_path must be a non-empty model path up to 500 characters.")
        if not isinstance(calibration["source_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", calibration["source_sha256"]):
            raise ValueError("reference_calibration.source_sha256 must be a lowercase SHA-256 hex digest.")
        if not isinstance(calibration["license"], str) or not calibration["license"].strip() or len(calibration["license"]) > 80:
            raise ValueError("reference_calibration.license must be a non-empty label up to 80 characters.")
        if calibration["use"] not in {"review_only", "geometry_seed"}:
            raise ValueError("reference_calibration.use must be 'review_only' or 'geometry_seed'.")
        geometry_seed_review = calibration.get("geometry_seed_review")
        if calibration["use"] == "geometry_seed":
            if not isinstance(geometry_seed_review, dict):
                raise ValueError("geometry_seed use requires an explicit geometry_seed_review attestation.")
            _object(
                geometry_seed_review,
                {"status", "reviewer", "reviewed_at_utc", "design_fit_reviewed", "topology_reviewed", "license_reviewed", "rationale"},
                "reference_calibration.geometry_seed_review",
            )
            if geometry_seed_review["status"] != "approved":
                raise ValueError("geometry_seed_review.status must be 'approved'.")
            if any(geometry_seed_review[field] is not True for field in
                   ("design_fit_reviewed", "topology_reviewed", "license_reviewed")):
                raise ValueError("geometry_seed use requires explicit design-fit, topology, and license review attestations.")
            if not isinstance(geometry_seed_review["reviewer"], str) or not geometry_seed_review["reviewer"].strip() or len(geometry_seed_review["reviewer"]) > 200:
                raise ValueError("geometry_seed_review.reviewer must contain 1 to 200 characters.")
            if not isinstance(geometry_seed_review["reviewed_at_utc"], str) or not geometry_seed_review["reviewed_at_utc"].strip():
                raise ValueError("geometry_seed_review.reviewed_at_utc must be an ISO date-time.")
            try:
                datetime.fromisoformat(geometry_seed_review["reviewed_at_utc"].replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("geometry_seed_review.reviewed_at_utc must be an ISO date-time.") from error
            if not isinstance(geometry_seed_review["rationale"], str) or not geometry_seed_review["rationale"].strip() or len(geometry_seed_review["rationale"]) > 2000:
                raise ValueError("geometry_seed_review.rationale must contain 1 to 2000 characters.")
        elif geometry_seed_review is not None:
            raise ValueError("geometry_seed_review is only valid when use is 'geometry_seed'.")
        measurement_ranges = {
            "width_over_height": (0, 5), "depth_over_height": (0, 5),
            "pelvis_height_percent": (0, 100), "shoulder_height_percent": (0, 100),
            "left_knee_height_percent": (0, 100), "left_ankle_height_percent": (0, 100),
            "head_height_percent": (0, 100), "left_eye_height_percent": (0, 100),
        }
        measurements = calibration["measurements"]
        if not isinstance(measurements, dict) or not measurements or set(measurements) - set(measurement_ranges):
            raise ValueError("reference_calibration.measurements must contain supported numeric measurement fields.")
        for field, number in measurements.items():
            minimum, maximum = measurement_ranges[field]
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not minimum <= number <= maximum:
                raise ValueError(f"reference_calibration.measurements.{field} must be a finite number from {minimum} to {maximum}.")

    concept = _object(top["concept"], {"archetype", "source_prompt", "design_summary", "assumptions"}, "concept")
    if not isinstance(concept["archetype"], str) or concept["archetype"] not in ARCHETYPES:
        raise ValueError(f"archetype must be one of: {', '.join(sorted(ARCHETYPES))}.")
    for field, maximum in (("source_prompt", 2000), ("design_summary", 1200)):
        text = concept[field]
        if not isinstance(text, str) or not text.strip() or len(text) > maximum:
            raise ValueError(f"concept.{field} must contain 1 to {maximum} characters.")
    assumptions = concept["assumptions"]
    if not isinstance(assumptions, list) or any(not isinstance(item, str) or not item.strip() or len(item) > 240 for item in assumptions):
        raise ValueError("concept.assumptions must be a list of non-empty strings up to 240 characters each.")

    body = _object(top["body"], set(RANGES), "body")
    for field, (minimum, maximum) in RANGES.items():
        number = body[field]
        if isinstance(number, bool) or not isinstance(number, int) or not minimum <= number <= maximum:
            raise ValueError(f"body.{field} must be an integer from {minimum} to {maximum}.")

    palette = _object(top["palette"], PALETTE_KEYS, "palette")
    for field, color in palette.items():
        if not isinstance(color, str) or not COLOR.fullmatch(color):
            raise ValueError(f"palette.{field} must be a six-digit hex color.")
    traits = _object(top["traits"], TRAIT_KEYS, "traits")
    if any(not isinstance(value, bool) for value in traits.values()):
        raise ValueError("Every traits value must be a boolean.")
    actions = top["actions"]
    if not isinstance(actions, list) or not actions or any(not isinstance(action, str) for action in actions):
        raise ValueError(f"actions must be a non-empty list using: {', '.join(sorted(ACTIONS))}.")
    if any(action not in ACTIONS for action in actions):
        raise ValueError(f"actions may use only: {', '.join(sorted(ACTIONS))}.")
    if len(set(actions)) != len(actions):
        raise ValueError("actions must not contain duplicates.")
    return json.loads(json.dumps(top))


def load_profile(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read profile {path}: {error}") from error
    return validate_profile(raw)
