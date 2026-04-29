#!/usr/bin/env python3
"""Init or resume a single job for a continuous conversation.

Design goals:
- One conversation key -> one active job directory under jobs/<SESSION_ID>/
- Create required subfolders and meta files if missing
- Persist mapping in jobs/_state/session_map.json

Typical usage (agent-side):
  SESSION_ID=$(./scripts/py skills/analysis-run/scripts/init_or_resume_job.py --key "channel:1483..." --prefix discord)
  export SESSION_ID

This script is workspace-level (not OpenClaw system-level). It enforces conventions by making the
standard path the easiest path.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _find_workspace_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "runtime").is_dir() and (candidate / "skills").is_dir():
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE_DIR = _find_workspace_root(Path(__file__).resolve())
JOBS_DIR = WORKSPACE_DIR / "jobs"
STATE_DIR = JOBS_DIR / "_state"
STATE_PATH = STATE_DIR / "session_map.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _sanitize_token(text: str, *, allow_colon: bool = False) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    if allow_colon:
        allowed.add(":")
    out = []
    for ch in str(text or "").strip():
        out.append(ch if ch in allowed else "_")
    cleaned = "".join(out).strip("_-")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned


def _generate_job_id(prefix: str, hint: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)
    pfx = _sanitize_token(prefix) or "job"
    h = _sanitize_token(hint) or ""
    parts = [pfx, ts]
    if h:
        parts.append(h[:32])
    parts.append(rand)
    return "-".join(parts)


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"version": 1, "updated_at": _now_iso(), "active": {}}
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    active = payload.get("active")
    if not isinstance(active, dict):
        active = {}
    return {
        "version": int(payload.get("version") or 1),
        "updated_at": str(payload.get("updated_at") or _now_iso()),
        "active": active,
    }


def _write_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = dict(state)
    state["updated_at"] = _now_iso()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_job_skeleton(job_dir: Path, session_id: str) -> None:
    (job_dir / "data").mkdir(parents=True, exist_ok=True)
    (job_dir / "profile").mkdir(parents=True, exist_ok=True)
    meta_dir = job_dir / ".meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    # Required meta files (create if missing)
    acq_log = meta_dir / "acquisition_log.jsonl"
    if not acq_log.exists():
        acq_log.write_text("", encoding="utf-8")

    artifact_index = meta_dir / "artifact_index.json"
    if not artifact_index.exists():
        artifact_index.write_text(
            json.dumps(
                {
                    "version": 1,
                    "job_id": session_id,
                    "created_at": _now_iso(),
                    "updated_at": _now_iso(),
                    "items": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    analysis_journal = meta_dir / "analysis_journal.md"
    if not analysis_journal.exists():
        analysis_journal.write_text(
            "# analysis journal\n\n- created_at: {ts}\n\n".format(ts=_now_iso()),
            encoding="utf-8",
        )

    req_timeline = meta_dir / "user_request_timeline.md"
    if not req_timeline.exists():
        req_timeline.write_text(
            "# user request timeline\n\n- created_at: {ts}\n\n".format(ts=_now_iso()),
            encoding="utf-8",
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Init or resume a job for a conversation key")
    ap.add_argument("--key", required=True, help="Conversation key (e.g. channel:xxxx)")
    ap.add_argument("--prefix", default="job", help="Prefix for job id (default: job)")
    ap.add_argument("--hint", default="", help="Optional hint to embed in job id")
    ap.add_argument("--force-new", action="store_true", help="Force create a new job even if mapping exists")
    ap.add_argument(
        "--print-export",
        action="store_true",
        help="Print shell export lines instead of only the id",
    )
    args = ap.parse_args()

    key = _sanitize_token(args.key, allow_colon=True)
    if not key:
        raise SystemExit("invalid --key")

    state = _load_state()
    active: dict[str, Any] = state["active"]

    session_id: str | None = None
    if not args.force_new:
        existing = active.get(key)
        if isinstance(existing, dict):
            sid = existing.get("job_id")
            if isinstance(sid, str) and sid.strip():
                session_id = sid.strip()

    # Create new job if needed
    if not session_id:
        for _ in range(50):
            candidate = _generate_job_id(args.prefix, args.hint)
            if not (JOBS_DIR / candidate).exists():
                session_id = candidate
                break
        if not session_id:
            raise SystemExit("failed to allocate unique job id")

        active[key] = {
            "job_id": session_id,
            "key": key,
            "created_at": _now_iso(),
            "last_used_at": _now_iso(),
            "prefix": _sanitize_token(args.prefix) or "job",
            "hint": _sanitize_token(args.hint)[:32] if args.hint else "",
        }
    else:
        # Update last_used_at
        existing = active.get(key)
        if isinstance(existing, dict):
            existing["last_used_at"] = _now_iso()
        else:
            active[key] = {"job_id": session_id, "key": key, "last_used_at": _now_iso()}

    job_dir = JOBS_DIR / session_id
    job_dir.mkdir(parents=True, exist_ok=True)
    _ensure_job_skeleton(job_dir, session_id)

    _write_state(state)

    if args.print_export:
        print(f"SESSION_ID={session_id}")
        print(f"export SESSION_ID={session_id}")
        print(f"# job_dir: {job_dir}")
    else:
        print(session_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
