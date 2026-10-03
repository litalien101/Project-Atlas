"""Compile a design profile and reviewed grammar into deterministic build inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/characters"))
from character_design_profile import load_profile  # noqa: E402


DEFAULT_GRAMMAR = ROOT / "art/characters/grammars/atlas_character_grammar_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_recipe(profile: dict, grammar: dict, profile_hash: str, grammar_hash: str,
                   include_draft_rules: bool = False) -> dict:
    if grammar.get("schema") != "atlas-character-grammar/v1":
        raise ValueError("Unsupported character grammar schema.")
    archetype = profile["concept"]["archetype"]
    rule = grammar.get("archetypes", {}).get(archetype)
    if rule is None:
        raise ValueError(f"Grammar has no archetype rule for {archetype!r}.")
    is_draft = rule.get("review_status") != "approved"
    if is_draft and not include_draft_rules:
        raise ValueError(f"Archetype rule {archetype!r} is draft; pass --allow-draft to build a review preview.")

    body = dict(profile["body"])
    multipliers = {**grammar["shared_defaults"]["proportion_multipliers"],
                   **rule.get("proportion_multipliers", {})}
    for dimension, factor in multipliers.items():
        field = f"{dimension}_percent"
        if field in body:
            body[field] = round(body[field] * factor)
    relationships = [item for item in grammar["anatomy_relationships"]
                     if item.get("review_status", "approved") == "approved" or include_draft_rules]
    return {
        "schema": "atlas-character-recipe/v1",
        "character_id": profile["character_id"],
        "profile_sha256": profile_hash,
        "grammar": {"id": grammar["grammar_id"], "revision": grammar["revision"], "sha256": grammar_hash},
        "builder": "atlas-parametric-body/v1",
        "body": body,
        "anatomy_relationships": relationships,
        "silhouette_tags": rule.get("silhouette_tags", []),
        "material_tags": rule.get("material_tags", []),
        "pose": grammar["shared_defaults"]["pose"],
        "evidence": rule.get("evidence", []),
        "draft_rules_applied": is_draft,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--grammar", type=Path, default=DEFAULT_GRAMMAR)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-draft", action="store_true", help="Allow generation from draft archetype rules for review only.")
    args = parser.parse_args()
    profile_path = args.profile.resolve(strict=True)
    grammar_path = args.grammar.resolve(strict=True)
    try:
        profile = load_profile(profile_path)
        grammar = json.loads(grammar_path.read_text(encoding="utf-8"))
        recipe = compile_recipe(profile, grammar, digest(profile_path), digest(grammar_path), args.allow_draft)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")
    print(f"Compiled {recipe['character_id']} with {recipe['grammar']['id']} r{recipe['grammar']['revision']} -> {output}")
    if recipe["draft_rules_applied"]:
        print("REVIEW: draft archetype rules were applied; model remains unapproved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
