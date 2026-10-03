#!/usr/bin/env python3
"""Validate an Atlas character observation and its review-state semantics."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "specs/atlas-character-observation-v1.schema.json"
VOCAB = ROOT / "specs/atlas-character-observation-vocabulary-v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observation", type=Path)
    args = parser.parse_args()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    vocabulary = json.loads(VOCAB.read_text(encoding="utf-8"))
    data = json.loads(args.observation.read_text(encoding="utf-8"))
    errors = [e for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data)]
    if data.get("schema") == "atlas-character-observation/v1":
        features = data.get("features", {})
        buckets = [features.get(k, []) for k in ("present", "absent", "unknown", "not_applicable")]
        memberships = {}
        for index, bucket in enumerate(buckets):
            for concept in bucket:
                memberships.setdefault(concept, set()).add(index)
        for concept, states in memberships.items():
            if len(states) > 1:
                errors.append(_error(f"feature {concept!r} appears in multiple state lists"))
        valid = {entry["concept_id"] for entry in vocabulary["concepts"]}
        for concept in memberships:
            if concept not in valid:
                errors.append(_error(f"feature {concept!r} is not in vocabulary revision {vocabulary['revision']}"))
        review = data.get("review", {})
        if review.get("status") == "reviewed":
            for field in ("reviewer", "reviewed_at_utc", "rationale"):
                if not review.get(field):
                    errors.append(_error(f"review.status=reviewed requires review.{field}"))
        for item in data.get("evidence_files", []):
            evidence_path = (args.observation.resolve().parent / item["path"]).resolve()
            if not evidence_path.is_file():
                errors.append(_error(f"evidence file does not exist: {item['path']}"))
                continue
            digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            if digest != item["sha256"]:
                errors.append(_error(f"evidence file hash mismatch: {item['path']}"))
    if errors:
        for error in errors:
            print(f"ERROR: {error.message}")
        return 1
    print(f"Valid observation: {args.observation}")
    return 0


class _Error:
    def __init__(self, message: str):
        self.message = message


def _error(message: str):
    return _Error(message)


if __name__ == "__main__":
    raise SystemExit(main())
