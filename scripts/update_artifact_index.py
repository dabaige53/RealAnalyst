#!/usr/bin/env python3
"""Upsert items into jobs/<SESSION_ID>/.meta/artifact_index.json.

This is a structured index for everything produced in a job:
- report (md/docx)
- analysis products (汇总_*.csv / 交叉_*.csv)
- raw exports (data/*.csv)
- profiling artifacts (profile/*.json)

To keep backward compatibility with legacy jobs, this script also writes a simplified
jobs/<SESSION_ID>/artifact_index.json summary (if possible).

Inputs:
- --item JSON string (repeatable)
- --from-duckdb-summary: add raw_data + audit items from duckdb_export_summary.json
- --set-report: set report path

It prints the updated .meta/artifact_index.json payload.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE_DIR = Path(__file__).resolve().parents[1]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _resolve_session_id(session_id: str | None) -> str:
    sid = (session_id or "").strip()
    if not sid:
        import os

        sid = (os.environ.get("SESSION_ID") or "").strip()
    if not sid:
        raise SystemExit("SESSION_ID_REQUIRED")
    return sid


def _job_dir(session_id: str) -> Path:
    jobs = WORKSPACE_DIR / "jobs" / session_id
    legacy = WORKSPACE_DIR / "temp" / session_id
    if legacy.exists() and not jobs.exists():
        return legacy
    return jobs


def _meta_dir(session_id: str) -> Path:
    return _job_dir(session_id) / ".meta"


def _relpath(path: str) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            return str(p.relative_to(WORKSPACE_DIR))
        except ValueError:
            return str(p)
    return str(p)


def _load_index(path: Path, session_id: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": 1,
            "job_id": session_id,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "items": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    payload.setdefault("version", 1)
    payload.setdefault("job_id", session_id)
    payload.setdefault("created_at", _now_iso())
    payload["items"] = items
    payload["updated_at"] = _now_iso()
    return payload


def _upsert(items: list[dict[str, Any]], item: dict[str, Any]) -> None:
    path = str(item.get("path") or "").strip()
    if not path:
        raise SystemExit("artifact item requires path")
    for idx, existing in enumerate(items):
        if not isinstance(existing, dict):
            continue
        if str(existing.get("path") or "").strip() == path:
            merged = dict(existing)
            merged.update(item)
            items[idx] = merged
            return
    items.append(item)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_root_summary(session_id: str, meta_index: dict[str, Any]) -> None:
    job = _job_dir(session_id)
    if not job.exists():
        return

    report_path: str | None = None
    artifacts: list[str] = []
    raw_data: list[str] = []

    for item in meta_index.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        p = str(item.get("path") or "")
        kind = str(item.get("kind") or "")
        role = str(item.get("role") or "")
        if kind == "report":
            report_path = p
        if role == "user" and p:
            artifacts.append(p)
        if kind == "raw_data" and p:
            raw_data.append(p)

    summary = {
        "job_id": session_id,
        "generated_at": _now_iso(),
        "report": report_path,
        "artifacts": sorted(set(artifacts)),
        "raw_data": sorted(set(raw_data)),
    }

    out = job / "artifact_index.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _from_duckdb_summary(path: Path, *, event_id: str | None) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("duckdb summary is not a json object")

    output_file = payload.get("output_file")
    if not isinstance(output_file, str) or not output_file:
        raise SystemExit("duckdb summary missing output_file")

    items: list[dict[str, Any]] = []

    items.append(
        {
            "path": _relpath(output_file),
            "kind": "raw_data",
            "role": "archive",
            "created_at": str(payload.get("exported_at") or _now_iso()),
            "source_backend": "duckdb",
            "source_id": payload.get("source_id"),
            "display_name": payload.get("display_name"),
            "event_id": event_id,
            "row_count": payload.get("row_count"),
        }
    )

    items.append(
        {
            "path": _relpath(str(path.relative_to(WORKSPACE_DIR)) if path.is_absolute() else str(path)),
            "kind": "audit",
            "role": "system",
            "created_at": str(payload.get("exported_at") or _now_iso()),
            "source_backend": "duckdb",
            "source_id": payload.get("source_id"),
            "event_id": event_id,
        }
    )

    return items


def main() -> int:
    ap = argparse.ArgumentParser(description="Update .meta/artifact_index.json")
    ap.add_argument("--session-id", default="", help="jobs/<session-id>/ (defaults to env SESSION_ID)")
    ap.add_argument("--set-report", default="", help="Report path to set (and upsert as kind=report, role=user)")
    ap.add_argument("--item", action="append", default=[], help="Artifact item JSON string (repeatable)")
    ap.add_argument("--from-duckdb-summary", default="", help="Path to duckdb_export_summary.json")
    ap.add_argument("--event-id", default="", help="Attach event_id to generated items")
    args = ap.parse_args()

    session_id = _resolve_session_id(args.session_id)
    job = _job_dir(session_id)
    job.mkdir(parents=True, exist_ok=True)
    meta = _meta_dir(session_id)
    meta.mkdir(parents=True, exist_ok=True)

    index_path = meta / "artifact_index.json"
    index = _load_index(index_path, session_id)

    items = index.get("items")
    if not isinstance(items, list):
        items = []
        index["items"] = items

    if args.set_report:
        rp = _relpath(args.set_report)
        _upsert(
            items,
            {
                "path": rp,
                "kind": "report",
                "role": "user",
                "created_at": _now_iso(),
            },
        )

    for raw in args.item or []:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise SystemExit("--item must be a json object")
        obj = dict(obj)
        if "path" in obj:
            obj["path"] = _relpath(str(obj["path"]))
        obj.setdefault("created_at", _now_iso())
        _upsert(items, obj)

    if args.from_duckdb_summary:
        event_id = args.event_id.strip() or None
        for it in _from_duckdb_summary(Path(args.from_duckdb_summary), event_id=event_id):
            _upsert(items, it)

    index["updated_at"] = _now_iso()
    _write_json(index_path, index)
    _write_root_summary(session_id, index)

    print(json.dumps(index, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
