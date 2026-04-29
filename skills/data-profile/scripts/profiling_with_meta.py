#!/usr/bin/env python3
"""Profiling wrapper with continuous-analysis metadata write-back.

It wraps:
  skills/data-profile/scripts/run.py

And then updates:
- jobs/<SESSION_ID>/.meta/artifact_index.json (profile outputs + input csv binding)

This helps keep profiling results traceable in a continuous-analysis job.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _find_workspace_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "runtime").is_dir() and (candidate / "skills").is_dir():
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE_DIR = _find_workspace_root(Path(__file__).resolve())


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _relpath(path: Path) -> str:
    if path.is_absolute():
        try:
            return str(path.relative_to(WORKSPACE_DIR))
        except ValueError:
            return str(path)
    return str(path)


def _job_dir(session_id: str) -> Path:
    jobs = WORKSPACE_DIR / "jobs" / session_id
    legacy = WORKSPACE_DIR / "temp" / session_id
    if legacy.exists() and not jobs.exists():
        return legacy
    return jobs


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True)


def _resolve_skill_script(*parts: str) -> Path:
    candidates = [
        WORKSPACE_DIR / "skills" / Path(*parts),
        WORKSPACE_DIR / ".agents" / "skills" / Path(*parts),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def main() -> int:
    ap = argparse.ArgumentParser(description="Profiling with metadata")
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--data-csv", default="", help="Explicit input csv")
    ap.add_argument("--output-dir", default="", help="Explicit output dir")
    ap.add_argument("--note", default="", help="Optional note to attach into artifact_index")
    args = ap.parse_args()

    session_id = args.session_id.strip()
    if not session_id:
        raise SystemExit("missing --session-id")

    profiling_script = _resolve_skill_script("data-profile", "scripts", "run.py")

    # Resolve output dir
    if args.output_dir.strip():
        out_dir = Path(args.output_dir).expanduser().resolve()
    else:
        out_dir = _job_dir(session_id)

    cmd = [
        str(WORKSPACE_DIR / "scripts" / "py"),
        str(profiling_script),
        "--output-dir",
        str(out_dir),
    ]
    if args.data_csv.strip():
        cmd += ["--data-csv", args.data_csv.strip()]

    proc = _run(cmd)
    # run.py prints JSON; keep stdout for debugging even on failure
    if proc.stdout:
        sys.stdout.write(proc.stdout)
        if not proc.stdout.endswith("\n"):
            sys.stdout.write("\n")

    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return proc.returncode

    payload = json.loads(proc.stdout)
    if not isinstance(payload, dict):
        raise SystemExit("profiling output is not a json object")

    data_csv = payload.get("data_csv")
    resolved_from = payload.get("resolved_from")

    manifest = out_dir / "profile" / "manifest.json"
    profile = out_dir / "profile" / "profile.json"

    items: list[dict[str, Any]] = []
    if manifest.exists():
        items.append(
            {
                "path": _relpath(manifest),
                "kind": "profile_manifest",
                "role": "system",
                "created_at": _now_iso(),
                "input_csv": data_csv,
                "resolved_from": resolved_from,
                "note": args.note or "",
            }
        )
    if profile.exists():
        items.append(
            {
                "path": _relpath(profile),
                "kind": "profile",
                "role": "system",
                "created_at": _now_iso(),
                "input_csv": data_csv,
                "resolved_from": resolved_from,
                "note": args.note or "",
            }
        )

    if items:
        idx_script = WORKSPACE_DIR / "scripts" / "update_artifact_index.py"
        idx_cmd = [
            str(WORKSPACE_DIR / "scripts" / "py"),
            str(idx_script),
            "--session-id",
            session_id,
        ]
        for it in items:
            idx_cmd += ["--item", json.dumps(it, ensure_ascii=False)]

        idx_proc = _run(idx_cmd)
        if idx_proc.returncode != 0:
            sys.stderr.write(idx_proc.stdout)
            sys.stderr.write(idx_proc.stderr)
            return idx_proc.returncode

    out = {
        "session_id": session_id,
        "output_dir": _relpath(out_dir),
        "data_csv": data_csv,
        "resolved_from": resolved_from,
        "profile_manifest": _relpath(manifest) if manifest.exists() else None,
        "profile": _relpath(profile) if profile.exists() else None,
        "updated_at": _now_iso(),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
