"""Archive failure evidence, then remove a rejected generated character.

Example:
  python tools/characters/archive_failed_candidate.py \
    --candidate-dir art/characters/exports/mpfb_female_prototype \
    --finding 'body_mask_removed_skin_at_opening|Review render showed neck skin cut away at the collar.|Keep body vertices within the garment opening clearance.'

Pass one or more --finding values in CODE|EVIDENCE|LESSON form. The command
verifies generated artifact hashes against build.json before archiving evidence
and deleting model binaries. It only accepts generated candidates under
art/characters/exports or art/characters/pending_models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_ROOTS = (
    ROOT / "art/characters/exports",
    ROOT / "art/characters/pending_models",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", required=True, type=Path)
    parser.add_argument(
        "--finding", required=True, action="append",
        help="Failure entry as CODE|EVIDENCE|LESSON; repeat for more findings.",
    )
    args = parser.parse_args()
    if not args.candidate_dir.is_absolute():
        args.candidate_dir = ROOT / args.candidate_dir
    args.candidate_dir = args.candidate_dir.resolve()
    for index, finding in enumerate(args.finding, start=1):
        parts = finding.split("|", 2)
        if len(parts) != 3 or any(not part.strip() for part in parts):
            parser.error(f"--finding {index} must have non-empty CODE|EVIDENCE|LESSON fields")
    if not any(args.candidate_dir.is_relative_to(base.resolve()) for base in ALLOWED_ROOTS):
        parser.error("candidate-dir must be inside art/characters/exports or pending_models")
    return args


def archive_candidate(candidate_dir: Path, findings: list[str]) -> Path:
    manifest_path = candidate_dir / "build.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"No build.json in candidate directory: {candidate_dir}")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    build_id = manifest.get("build_id")
    if not isinstance(build_id, str) or not build_id:
        raise ValueError("build.json has no valid build_id")

    records_path = ROOT / "art/characters/failure_records/mpfb_prototype_attempts.json"
    records = json.loads(records_path.read_text(encoding="utf-8"))
    if any(entry.get("build_id") == build_id for entry in records.get("attempts", [])):
        raise ValueError(f"Failure record already exists for build {build_id}")

    artifact_rows = []
    for output in manifest.get("outputs", {}).values():
        filename = output.get("path")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError(f"Unsafe output path in build manifest: {filename!r}")
        artifact = candidate_dir / filename
        if not artifact.is_file():
            raise FileNotFoundError(f"Manifest output is missing: {artifact}")
        digest = sha256(artifact)
        if digest != output.get("sha256"):
            raise ValueError(f"Hash mismatch for {artifact}; refusing to archive/delete")
        artifact_rows.append({
            "name": artifact.name,
            "bytes": artifact.stat().st_size,
            "sha256": digest,
            "disposition": "deleted_after_verified_manifest_archive",
        })

    backups = []
    for backup in sorted(candidate_dir.glob("*.blend1")):
        backups.append({
            "name": backup.name,
            "bytes": backup.stat().st_size,
            "sha256": sha256(backup),
            "disposition": "deleted_blender_backup",
        })

    manifests_dir = ROOT / "art/characters/failure_records/manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    archived_manifest = manifests_dir / f"{build_id}.json"
    if archived_manifest.exists() and archived_manifest.read_bytes() != manifest_bytes:
        raise FileExistsError(f"A different manifest is already archived at {archived_manifest}")
    if not archived_manifest.exists():
        archived_manifest.write_bytes(manifest_bytes)

    parsed_findings = [
        dict(zip(("code", "evidence", "lesson"), (part.strip() for part in finding.split("|", 2))))
        for finding in findings
    ]
    records.setdefault("attempts", []).append({
        "build_id": build_id,
        "disposition": "superseded_failed_attempt",
        "failure_codes": [finding["code"] for finding in parsed_findings],
        "findings": parsed_findings,
        "artifacts_at_cleanup": artifact_rows,
        "blender_backups_at_cleanup": backups,
        "build_manifest_path": str(archived_manifest.relative_to(ROOT)),
        "build_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    })
    records["updated_at_utc"] = datetime.now(timezone.utc).date().isoformat()
    old_current = records.get("current_candidate")
    if old_current:
        current_path = (ROOT / old_current).resolve()
        if current_path == candidate_dir or current_path.is_relative_to(candidate_dir):
            records["current_candidate"] = None

    temporary = records_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    temporary.replace(records_path)

    for row in artifact_rows + backups:
        (candidate_dir / row["name"]).unlink()
    manifest_path.unlink()
    try:
        candidate_dir.rmdir()
    except OSError:
        pass  # Keep unexpected, untracked files for manual review.
    return archived_manifest


if __name__ == "__main__":
    args = parse_args()
    print(archive_candidate(args.candidate_dir, args.finding))
