"""Validate an Atlas character design profile."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from character_design_profile import load_profile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    try:
        profile = load_profile(args.profile)
    except ValueError as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1
    print(f"VALID: {profile['character_id']} ({profile['concept']['archetype']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
