#!/usr/bin/env python3
"""Build the final delivery checklist for a RealAnalyst job.

The script does not upload files. It creates a machine-readable manifest that
agents can use as the final gate before replying in Slack, email, or another
delivery channel.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _find_workspace_root(start: Path) -> Path:
    env_root = os.environ.get("ANALYST_WORKSPACE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()
    for candidate in (start, *start.parents):
        if (candidate / "runtime").is_dir() and (
            (candidate / "skills").is_dir() or (candidate / ".agents" / "skills").is_dir()
        ):
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE = _find_workspace_root(Path(__file__).resolve())


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _job_dir(session_id: str) -> Path:
    return WORKSPACE / "jobs" / session_id


def _safe_rel(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return str(resolved.relative_to(WORKSPACE.resolve()))
    except ValueError as exc:
        raise SystemExit(f"DELIVERY_PATH_OUTSIDE_WORKSPACE: {resolved}") from exc


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_job_path(job: Path, value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        return raw.expanduser().resolve()
    candidates = [(WORKSPACE / raw).resolve(), (job / raw).resolve()]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _files_from_meta_index(job: Path) -> list[Path]:
    payload = _load_json(job / ".meta" / "artifact_index.json")
    files: list[Path] = []
    for item in payload.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        role = str(item.get("role") or "")
        rel = str(item.get("path") or "").strip()
        if not rel:
            continue
        if kind == "report" or role == "user":
            files.append(_resolve_job_path(job, rel))
    return files


def _files_from_root_index(job: Path) -> list[Path]:
    payload = _load_json(job / "artifact_index.json")
    files: list[Path] = []
    report = payload.get("report")
    if isinstance(report, str) and report.strip():
        files.append(_resolve_job_path(job, report))
    for rel in payload.get("artifacts", []) or []:
        if isinstance(rel, str) and rel.strip():
            files.append(_resolve_job_path(job, rel))
    return files


def _scan_job_outputs(job: Path) -> list[Path]:
    patterns = ("报告_*.md", "report.md", "汇总_*.csv", "交叉_*.csv")
    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(job.glob(pattern)))
    return files


def _dedupe(files: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for file in files:
        resolved = file.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def _load_upload_receipt(path: str) -> dict[str, Any]:
    if not path:
        return {}
    payload = _load_json(Path(path).expanduser().resolve())
    return payload


def build_manifest(session_id: str, *, platform: str, upload_receipt: str = "") -> dict[str, Any]:
    job = _job_dir(session_id)
    if not job.exists():
        raise SystemExit(f"JOB_NOT_FOUND: {job}")

    required = _dedupe(_files_from_meta_index(job) + _files_from_root_index(job) + _scan_job_outputs(job))
    files = [
        {
            "path": _safe_rel(path),
            "kind": "report" if path.suffix.lower() == ".md" else "attachment",
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else None,
        }
        for path in required
    ]
    missing = [item["path"] for item in files if not item["exists"]]
    report_files = [item for item in files if item["kind"] == "report" and item["exists"]]
    receipt = _load_upload_receipt(upload_receipt)
    uploaded = bool(receipt.get("success") or receipt.get("ok"))

    if missing or not report_files:
        status = "blocked"
    elif uploaded:
        status = "delivered"
    else:
        status = "ready_for_upload"

    return {
        "job_id": session_id,
        "generated_at": _now_iso(),
        "platform": platform,
        "status": status,
        "required_delivery_files": files,
        "missing_files": missing,
        "upload_receipt": receipt,
        "final_reply_contract": {
            "must_attach_report_file": True,
            "must_attach_user_csv_artifacts": True,
            "must_hide_internal_paths_unless_requested": True,
            "if_upload_fails": "Tell the user the report is generated but file upload failed, then retry or provide a concrete recovery path.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build final delivery_manifest.json for a RealAnalyst job.")
    parser.add_argument("--session-id", default=os.environ.get("SESSION_ID", ""), help="jobs/<session-id>")
    parser.add_argument("--platform", default="slack", help="Delivery platform name, e.g. slack/email/drive")
    parser.add_argument("--upload-receipt-json", default="", help="Optional JSON receipt from the external uploader")
    args = parser.parse_args()

    session_id = args.session_id.strip()
    if not session_id:
        raise SystemExit("SESSION_ID_REQUIRED")
    manifest = build_manifest(session_id, platform=args.platform, upload_receipt=args.upload_receipt_json)
    out = _job_dir(session_id) / "delivery_manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": manifest["status"] != "blocked", "status": manifest["status"], "delivery_manifest": _safe_rel(out)}, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
