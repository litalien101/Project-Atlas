"""Validate a versioned Atlas cross-category model recipe."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_recipe_pipeline import validate_recipe  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path, help="Recipe JSON to validate")
    parser.add_argument(
        "--skip-file-checks", action="store_true",
        help="Validate schema and references without opening referenced files",
    )
    args = parser.parse_args()
    try:
        recipe_path = args.recipe.resolve(strict=True)
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        errors = validate_recipe(recipe, recipe_path, check_files=not args.skip_file_checks)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1
    if errors:
        print("INVALID: model recipe failed validation", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"VALID: {recipe['recipe_id']} revision {recipe['revision']} ({recipe['schema']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
