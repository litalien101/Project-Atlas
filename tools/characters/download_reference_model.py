"""Fetch pinned, permissively licensed character-model authoring references."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "art/characters/.source_cache"
SOURCES = {
    "troll-mauler": {
        "url": "https://opengameart.org/sites/default/files/troll.blend",
        "filename": "troll-mauler-piacenti.blend",
        "sha256": "83fc5e524d31020d8b7c9641517f965cecd65840b3119582b4e984649f708c51",
        "license": "CC-BY-3.0",
    },
    "blender-human-bases": {
        "url": "https://download.blender.org/demo/asset-bundles/human-base-meshes/human-base-meshes-bundle-v1.4.1.zip",
        "filename": "human-base-meshes-bundle-v1.4.1.zip",
        "sha256": "811f43accbb31a88266d932f8f5563b2d13586fca0ba2693aad1f5fe582b3515",
        "license": "CC0-1.0",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=sorted(SOURCES))
    parser.add_argument("--output-dir", type=Path, default=CACHE)
    args = parser.parse_args()

    source = SOURCES[args.model]
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / source["filename"]
    if destination.exists():
        if sha256(destination) == source["sha256"]:
            print(f"Already present and verified ({source['license']}): {destination}")
            return 0
        print(f"Refusing to overwrite a file with an unexpected checksum: {destination}", file=sys.stderr)
        return 1

    partial = destination.with_name(destination.name + ".part")
    request = urllib.request.Request(
        source["url"], headers={"User-Agent": "Project-Atlas-reference-fetcher/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("xb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        actual = sha256(partial)
        if actual != source["sha256"]:
            partial.unlink(missing_ok=True)
            print(f"Checksum mismatch; expected {source['sha256']}, received {actual}", file=sys.stderr)
            return 1
        os.replace(partial, destination)
    except (OSError, urllib.error.URLError) as error:
        partial.unlink(missing_ok=True)
        print(f"Could not download {args.model}: {error}", file=sys.stderr)
        return 1

    print(f"Downloaded and SHA-256 verified ({source['license']}): {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
