"""Compare an Atlas-generated character with an extracted reference calibration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--generated-calibration", type=Path, required=True)
    parser.add_argument("--character-record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    reference, generated, character = map(read, (args.reference, args.generated_calibration, args.character_record))
    target_height = character["design_profile"]["body"]["height_cm"] / 100
    source_sections = {item["height_percent"]: item for item in reference["geometry"]["cross_sections"]}
    generated_sections = {item["height_percent"]: item for item in generated["geometry"]["cross_sections"]}
    sections = []
    for height in sorted(source_sections.keys() & generated_sections.keys()):
        source, result = source_sections[height], generated_sections[height]
        sections.append({
            "height_percent": height,
            "x_extent_delta_over_height": round(result["x_extent_over_height"] - source["x_extent_over_height"], 6),
            "y_extent_delta_over_height": round(result["y_extent_over_height"] - source["y_extent_over_height"], 6),
            "source_sample_vertices": source["sample_vertices"],
            "generated_sample_vertices": result["sample_vertices"],
        })

    marker_map = {
        "pelvis": "hip_left", "left_knee": "knee_left", "left_ankle": "ankle_left",
        "left_shoulder": "shoulder_left", "head": "head", "left_eye": "eye_left",
    }
    landmarks = {}
    for reference_name, character_name in marker_map.items():
        source = reference["rig"]["landmarks"].get(reference_name)
        point = character.get("anatomical_landmarks", {}).get(character_name)
        if source and point:
            generated_percent = point[2] / target_height * 100
            landmarks[reference_name] = {
                "generated_height_percent": round(generated_percent, 3),
                "reference_height_percent": source["height_percent"],
                "delta_percentage_points": round(generated_percent - source["height_percent"], 3),
            }

    source_geometry, result_geometry = reference["geometry"], generated["geometry"]
    reference_path = args.reference.resolve()
    try:
        reference_location = str(reference_path.relative_to(ROOT))
    except ValueError:
        reference_location = str(reference_path)
    comparison = {
        "schema": "atlas-character-reference-comparison/v1",
        "character_id": character["character_id"],
        "reference_calibration": reference_location,
        "reference_source_sha256": reference["source_sha256"],
        "generated_preview_sha256": character["sha256"]["preview_glb"],
        "generated_profile_sha256": character["sha256"]["design_profile"],
        "generator_version": character["generator_version"],
        "whole_mesh": {
            "width_over_height_delta": round(result_geometry["width_over_height"] - source_geometry["width_over_height"], 6),
            "depth_over_height_delta": round(result_geometry["depth_over_height"] - source_geometry["depth_over_height"], 6),
            "caveat": "Whole-mesh extents include the source character's posed arms, ears, and protrusions.",
        },
        "normalized_landmarks": landmarks,
        "cross_section_deltas": sections,
        "review_guidance": [
            "Landmark ratios describe this source rig's rest-pose bone heads and are comparison guides, not automatic rig targets.",
            "Cross-sections include whatever geometry intersects each horizontal slice; inspect sample counts and use a visual review before changing recipe controls.",
            "The comparison is diagnostic. It does not imply source geometry, materials, rigging, or animation were copied.",
        ],
    }
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(f"Comparison: {output}")
    print("Landmark deltas (percentage points): " + ", ".join(
        f"{name} {item['delta_percentage_points']:+.2f}" for name, item in landmarks.items()
    ))


if __name__ == "__main__":
    main()
