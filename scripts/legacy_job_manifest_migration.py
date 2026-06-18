#!/usr/bin/env python3
"""Dry-run legacy job manifest migration.

This script scans one existing job directory and emits a candidate
job_manifest.json payload plus a short review report. It never writes, moves, or
deletes files.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE_DIR = Path(__file__).resolve().parents[1]
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from runtime import job_manifest


INTERNAL_NAMES = {
    "artifact_index.json",
    "export_summary.json",
    "duckdb_export_summary.json",
    "mysql_export_summary.json",
    "clickhouse_export_summary.json",
    "data_export_summary.json",
    "verification.json",
    "analysis.json",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _rel(job_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(job_dir.resolve()).as_posix()


def _artifact_id(kind: str, rel_path: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in Path(rel_path).stem).strip("_")[:40]
    return f"legacy_{kind}_{cleaned or 'artifact'}"


def classify_artifact(job_dir: Path, path: Path) -> dict[str, Any]:
    rel_path = _rel(job_dir, path)
    name = path.name
    suffix = path.suffix.lower()
    parts = set(Path(rel_path).parts)

    role = "unknown_legacy"
    kind = "other"
    user_visible = False
    safe_to_archive = True

    if ".meta" in parts or name in INTERNAL_NAMES:
        role = "audit_log"
        kind = "json" if suffix in {".json", ".jsonl"} else "markdown" if suffix == ".md" else "other"
    elif "profile" in parts:
        role = "derived_internal"
        kind = "json" if suffix == ".json" else "other"
    elif "data" in parts:
        role = "raw_input"
        kind = "csv" if suffix == ".csv" else "other"
    elif suffix == ".md" and (name.startswith("报告") or "report" in name.lower()):
        role = "user_deliverable"
        kind = "markdown"
        user_visible = True
        safe_to_archive = False
    elif suffix in {".csv", ".xlsx", ".docx", ".pptx"} and (
        name.startswith("汇总") or name.startswith("交叉") or name.startswith("报告")
    ):
        role = "user_attachment"
        kind = "csv" if suffix == ".csv" else "other"
        user_visible = True
        safe_to_archive = False
    elif suffix == ".json":
        role = "audit_log"
        kind = "json"
    elif suffix == ".md":
        kind = "markdown"

    return {
        "id": _artifact_id(kind, rel_path),
        "role": role,
        "kind": kind,
        "display_name": path.stem,
        "path": rel_path,
        "producer": "legacy-migration-dry-run",
        "consumers": [],
        "created_at": _now_iso(),
        "status": "ready",
        "validation": {"status": "not_run"},
        "user_visible": user_visible,
        "internal_only": not user_visible,
        "safe_to_archive": safe_to_archive,
        "safe_to_delete": False,
    }


def build_candidate_manifest(job_dir: Path) -> dict[str, Any]:
    payload = job_manifest.default_manifest(job_id=job_dir.name, title=job_dir.name, owner_skill="legacy-migration")
    payload["job"]["status"] = "ready_for_review"
    payload["legacy"] = {
        "source": "legacy_job_manifest_migration.py",
        "dry_run": True,
        "scanned_at": _now_iso(),
    }

    artifacts: list[dict[str, Any]] = []
    for path in sorted(job_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name == job_manifest.MANIFEST_NAME:
            continue
        artifact = classify_artifact(job_dir, path)
        artifacts.append(artifact)

    payload["artifacts"] = artifacts
    deliverable_ids = [
        artifact["id"]
        for artifact in artifacts
        if artifact["role"] in job_manifest.USER_VISIBLE_ROLES and artifact["user_visible"]
    ]
    payload["user_surface"]["deliverables"] = deliverable_ids
    payload["user_surface"]["primary_deliverable_id"] = deliverable_ids[0] if deliverable_ids else None
    if deliverable_ids:
        payload["user_surface"]["summary"] = "已识别历史用户可见交付物，待人工确认。"
    return payload


def render_review(candidate: dict[str, Any]) -> str:
    artifacts = candidate.get("artifacts") or []
    role_counts: dict[str, int] = {}
    unknown: list[str] = []
    visible: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        role = str(artifact.get("role") or "unknown_legacy")
        role_counts[role] = role_counts.get(role, 0) + 1
        if role == "unknown_legacy":
            unknown.append(str(artifact.get("path") or ""))
        if artifact.get("user_visible"):
            visible.append(str(artifact.get("display_name") or artifact.get("path") or ""))

    lines = [
        "# Legacy Job Manifest Dry Run Review",
        "",
        f"- Job: {candidate.get('job', {}).get('id', '')}",
        f"- Artifacts scanned: {len(artifacts)}",
        f"- User-visible candidates: {len(visible)}",
        f"- Unknown legacy items: {len(unknown)}",
        "",
        "## Role Counts",
        "",
    ]
    for role, count in sorted(role_counts.items()):
        lines.append(f"- {role}: {count}")
    lines += ["", "## User-Visible Candidates", ""]
    lines.extend([f"- {name}" for name in visible] or ["- None"])
    lines += ["", "## Unknown Legacy Items", ""]
    lines.extend([f"- {path}" for path in unknown] or ["- None"])
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run legacy job_manifest.json migration.")
    parser.add_argument("--job-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    job_dir = Path(args.job_dir).expanduser().resolve()
    if not job_dir.exists() or not job_dir.is_dir():
        print(
            json.dumps(
                {"success": False, "error": f"job dir not found: {job_dir}", "error_code": "JOB_DIR_NOT_FOUND"},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    candidate = build_candidate_manifest(job_dir)
    review = render_review(candidate)
    result = {
        "success": True,
        "dry_run": True,
        "job_dir": str(job_dir),
        "candidate_manifest": candidate,
        "review_markdown": review,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
