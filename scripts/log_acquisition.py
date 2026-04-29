#!/usr/bin/env python3
"""Append a single acquisition record into jobs/<SESSION_ID>/.meta/acquisition_log.jsonl.

This is the durable audit trail for *each* data download/export inside a continuous-analysis job.

Supported inputs:
- --json / --json-file: provide a record directly
- --from-duckdb-summary: build record from duckdb_export_summary.json
- --from-tableau-run: build record from the JSON printed by tableau export_source.py

The script will always add:
- event_id (uuid)
- event_type = "acquisition"
- logged_at (ISO timestamp)
- session_id

It prints the final record as JSON to stdout.
"""

from __future__ import annotations

import argparse
import json
import uuid
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


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_meta_files(session_id: str) -> Path:
    meta = _meta_dir(session_id)
    meta.mkdir(parents=True, exist_ok=True)
    log_path = meta / "acquisition_log.jsonl"
    if not log_path.exists():
        log_path.write_text("", encoding="utf-8")
    return log_path


def _build_from_duckdb_summary(path: Path, *, reason: str, confirmed: bool, is_new_source: bool) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise SystemExit("duckdb summary is not a json object")
    record: dict[str, Any] = {
        "source_backend": "duckdb",
        "source_id": payload.get("source_id"),
        "display_name": payload.get("display_name"),
        "db_path": payload.get("db_path"),
        "object_name": payload.get("object_name"),
        "output_file": payload.get("output_file"),
        "row_count": payload.get("row_count"),
        "selected_fields": payload.get("selected_fields"),
        "filters": payload.get("filters"),
        "date_ranges": payload.get("date_ranges"),
        "group_by": payload.get("group_by"),
        "aggregates": payload.get("aggregates"),
        "order_by": payload.get("order_by"),
        "limit": payload.get("limit"),
        "exported_at": payload.get("exported_at"),
        "reason": reason or "",
        "confirmed_by_user": bool(confirmed),
        "is_new_source": bool(is_new_source),
        "summary_file": str(path.relative_to(WORKSPACE_DIR)) if path.is_absolute() else str(path),
    }
    return record


def _build_from_tableau_run(path: Path, *, reason: str, confirmed: bool, is_new_source: bool) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise SystemExit("tableau run summary is not a json object")

    record: dict[str, Any] = {
        "source_backend": "tableau",
        "source_id": payload.get("source_id"),
        "display_name": payload.get("display_name"),
        "type": payload.get("type"),
        "timestamp": payload.get("timestamp"),
        "views": payload.get("views"),
        "source_context_path": payload.get("source_context_path"),
        "context_injection_path": payload.get("context_injection_path"),
        "reason": reason or "",
        "confirmed_by_user": bool(confirmed),
        "is_new_source": bool(is_new_source),
        "run_summary_file": str(path.relative_to(WORKSPACE_DIR)) if path.is_absolute() else str(path),
    }
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description="Append acquisition record (jsonl)")
    ap.add_argument("--session-id", default="", help="jobs/<session-id>/ (defaults to env SESSION_ID)")

    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--json", help="Record JSON string")
    src.add_argument("--json-file", help="Path to a JSON file containing the record")
    src.add_argument("--from-duckdb-summary", help="Path to duckdb_export_summary.json")
    src.add_argument("--from-tableau-run", help="Path to tableau export_source.py stdout JSON")

    ap.add_argument("--reason", default="", help="Why this acquisition happened")
    ap.add_argument("--confirmed", action="store_true", help="User confirmed (required for new sources)")
    ap.add_argument("--is-new-source", action="store_true", help="Whether this acquisition introduces a new source")

    args = ap.parse_args()

    session_id = _resolve_session_id(args.session_id)
    _job_dir(session_id).mkdir(parents=True, exist_ok=True)
    log_path = _ensure_meta_files(session_id)

    if args.json:
        base = json.loads(args.json)
        if not isinstance(base, dict):
            raise SystemExit("--json must be a json object")
        record = base
    elif args.json_file:
        record = _load_json(Path(args.json_file))
        if not isinstance(record, dict):
            raise SystemExit("--json-file must contain a json object")
    elif args.from_duckdb_summary:
        record = _build_from_duckdb_summary(
            Path(args.from_duckdb_summary),
            reason=args.reason,
            confirmed=args.confirmed,
            is_new_source=args.is_new_source,
        )
    elif args.from_tableau_run:
        record = _build_from_tableau_run(
            Path(args.from_tableau_run),
            reason=args.reason,
            confirmed=args.confirmed,
            is_new_source=args.is_new_source,
        )
    else:
        raise SystemExit("no input")

    # Normalize + enrich
    enriched: dict[str, Any] = dict(record)
    enriched.setdefault("event_type", "acquisition")
    enriched["event_id"] = str(uuid.uuid4())
    enriched["logged_at"] = _now_iso()
    enriched["session_id"] = session_id

    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(enriched, ensure_ascii=False) + "\n")

    print(json.dumps(enriched, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
