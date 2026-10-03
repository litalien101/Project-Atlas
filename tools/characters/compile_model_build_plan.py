"""Validate a model recipe and write a deterministic, candidate-only build plan."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_recipe_pipeline import compile_build_plan, validate_recipe  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path, help="Validated atlas-model-recipe/v1 JSON")
    parser.add_argument("--output", type=Path, required=True, help="Build-plan JSON output path")
    parser.add_argument(
        "--skip-file-checks", action="store_true",
        help="Skip opening/checksumming recipe file references (not recommended)",
    )
    args = parser.parse_args()
    try:
        recipe_path = args.recipe.resolve(strict=True)
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        errors = validate_recipe(recipe, recipe_path, check_files=not args.skip_file_checks)
        if errors:
            print("BLOCKED: recipe validation failed", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        plan = compile_build_plan(recipe, recipe_path)
        output_path = args.output.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=output_path.parent,
            prefix=f".{output_path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(plan, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, output_path)
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 1
    print(f"BUILD PLAN: {output_path} (candidate only; runtime release is blocked)")
    print(f"Plan SHA-256: {plan['plan_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
