#!/usr/bin/env python3
"""Finalize delivered jobs by reviewing or applying internal archive moves.

Default mode is dry-run and never changes files. Apply mode requires both
--apply and --confirm-delivered, and only works for delivered jobs.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE_DIR = Path(__file__).resolve().parents[1]
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from runtime import job_manifest


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _candidate_artifacts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for artifact in manifest.get("artifacts", []) or []:
        if not isinstance(artifact, dict):
            continue
        if artifact.get("user_visible") is True:
            continue
        if artifact.get("internal_only") is not True:
            continue
        if artifact.get("safe_to_archive") is not True:
            continue
        if artifact.get("status") != "ready":
            continue
        candidates.append(artifact)
    return candidates


def _render_review(manifest: dict[str, Any], candidates: list[dict[str, Any]], *, can_apply: bool) -> str:
    lines = [
        "# Delivered Job Archive Review",
        "",
        f"- Job: {manifest.get('job', {}).get('id', '')}",
        f"- Job status: {manifest.get('job', {}).get('status', '')}",
        f"- Can apply: {'yes' if can_apply else 'no'}",
        f"- Archive candidates: {len(candidates)}",
        "",
        "## Candidates",
        "",
    ]
    if candidates:
        for artifact in candidates:
            lines.append(
                f"- {artifact.get('path', '')} ({artifact.get('role', '')}, {artifact.get('kind', '')})"
            )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def build_review(job_dir: Path) -> dict[str, Any]:
    manifest = job_manifest.load_manifest(job_dir)
    status = manifest.get("job", {}).get("status")
    can_apply = status == "delivered"
    candidates = _candidate_artifacts(manifest) if can_apply else []
    return {
        "success": True,
        "dry_run": True,
        "can_apply": can_apply,
        "job_status": status,
        "candidate_count": len(candidates),
        "candidates": [
            {
                "id": artifact.get("id"),
                "path": artifact.get("path"),
                "role": artifact.get("role"),
                "kind": artifact.get("kind"),
            }
            for artifact in candidates
        ],
        "review_markdown": _render_review(manifest, candidates, can_apply=can_apply),
    }


def apply_archive(job_dir: Path, *, confirm_delivered: bool) -> dict[str, Any]:
    manifest = job_manifest.load_manifest(job_dir)
    status = manifest.get("job", {}).get("status")
    if status != "delivered" or not confirm_delivered:
        return {
            "success": False,
            "error": "archive apply requires delivered job status and --confirm-delivered",
            "error_code": "ARCHIVE_CONFIRMATION_REQUIRED",
            "job_status": status,
        }

    candidates = _candidate_artifacts(manifest)
    archive_root = job_dir / ".archive" / "internal"
    moved: list[dict[str, str]] = []
    now = _now_iso()

    artifacts = manifest.get("artifacts", [])
    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact not in candidates:
            continue
        original_rel = str(artifact.get("path") or "")
        original = (job_dir / original_rel).resolve()
        try:
            original.relative_to(job_dir.resolve())
        except ValueError:
            continue
        if not original.exists() or not original.is_file():
            continue
        archived = archive_root / original_rel
        archived.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(original), str(archived))
        archived_rel = archived.relative_to(job_dir).as_posix()
        artifact["archive"] = {
            "original_path": original_rel,
            "archived_path": archived_rel,
            "archived_at": now,
        }
        artifact["path"] = archived_rel
        artifact["status"] = "archived"
        artifact["safe_to_archive"] = False
        moved.append({"id": str(artifact.get("id")), "from": original_rel, "to": archived_rel})

    manifest["artifacts"] = artifacts
    manifest["job"]["status"] = "archived"
    manifest["archive"] = {
        **(manifest.get("archive") if isinstance(manifest.get("archive"), dict) else {}),
        "archived_at": now,
        "archive_root": ".archive/internal",
        "moved_count": len(moved),
        "moved": moved,
    }
    job_manifest.save_manifest(job_dir, manifest)
    return {"success": True, "dry_run": False, "moved_count": len(moved), "moved": moved}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review or apply delivered job internal archive.")
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-delivered", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    job_dir = Path(args.job_dir).expanduser().resolve()
    try:
        result = apply_archive(job_dir, confirm_delivered=args.confirm_delivered) if args.apply else build_review(job_dir)
    except Exception as exc:
        result = {
            "success": False,
            "error": str(exc),
            "error_code": getattr(exc, "error_code", "FINALIZE_JOB_ARCHIVE_ERROR"),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
