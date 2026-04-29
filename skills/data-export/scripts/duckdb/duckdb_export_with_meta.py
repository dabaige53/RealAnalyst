#!/usr/bin/env python3
"""DuckDB export wrapper with continuous-analysis metadata write-back.

It wraps:
  skills/data-export/scripts/duckdb/export_duckdb_source.py

And then:
- appends acquisition record into .meta/acquisition_log.jsonl
- updates .meta/artifact_index.json (and root artifact_index.json summary)

This makes the compliant path the default path.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

def _find_workspace_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "runtime").is_dir() and (candidate / "skills").is_dir():
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE_DIR = _find_workspace_root(Path(__file__).resolve())


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
    ap = argparse.ArgumentParser(description="DuckDB export with metadata")
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--output-name", required=True)
    ap.add_argument("--select")
    ap.add_argument("--filter", action="append", default=[])
    ap.add_argument("--date-range", action="append", default=[])
    ap.add_argument("--group-by")
    ap.add_argument("--aggregate", action="append", default=[])
    ap.add_argument("--order-by", action="append", default=[])
    ap.add_argument("--limit", type=int)

    ap.add_argument("--reason", default="")
    ap.add_argument("--confirmed", action="store_true")
    ap.add_argument("--is-new-source", action="store_true")

    args = ap.parse_args()

    export_script = _resolve_skill_script("data-export", "scripts", "duckdb", "export_duckdb_source.py")
    cmd = [
        str(WORKSPACE_DIR / "scripts" / "py"),
        str(export_script),
        "--source-id",
        args.source_id,
        "--session-id",
        args.session_id,
        "--output-name",
        args.output_name,
    ]
    if args.select:
        cmd += ["--select", args.select]
    for f in args.filter or []:
        cmd += ["--filter", f]
    for dr in args.date_range or []:
        cmd += ["--date-range", dr]
    if args.group_by:
        cmd += ["--group-by", args.group_by]
    for agg in args.aggregate or []:
        cmd += ["--aggregate", agg]
    for ob in args.order_by or []:
        cmd += ["--order-by", ob]
    if args.limit is not None:
        cmd += ["--limit", str(args.limit)]

    proc = _run(cmd)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return proc.returncode

    run_payload = json.loads(proc.stdout)
    summary_file = run_payload.get("summary_file")
    if not isinstance(summary_file, str) or not summary_file:
        raise SystemExit("missing summary_file from export")

    summary_path = Path(summary_file)

    # 1) log acquisition
    log_script = WORKSPACE_DIR / "scripts" / "log_acquisition.py"
    log_cmd = [
        str(WORKSPACE_DIR / "scripts" / "py"),
        str(log_script),
        "--session-id",
        args.session_id,
        "--from-duckdb-summary",
        str(summary_path),
        "--reason",
        args.reason,
    ]
    if args.confirmed:
        log_cmd.append("--confirmed")
    if args.is_new_source:
        log_cmd.append("--is-new-source")

    log_proc = _run(log_cmd)
    if log_proc.returncode != 0:
        sys.stderr.write(log_proc.stdout)
        sys.stderr.write(log_proc.stderr)
        return log_proc.returncode

    log_payload = json.loads(log_proc.stdout)
    event_id = log_payload.get("event_id")

    # 2) update artifact index
    idx_script = WORKSPACE_DIR / "scripts" / "update_artifact_index.py"
    idx_cmd = [
        str(WORKSPACE_DIR / "scripts" / "py"),
        str(idx_script),
        "--session-id",
        args.session_id,
        "--from-duckdb-summary",
        str(summary_path),
    ]
    if isinstance(event_id, str) and event_id:
        idx_cmd += ["--event-id", event_id]

    idx_proc = _run(idx_cmd)
    if idx_proc.returncode != 0:
        sys.stderr.write(idx_proc.stdout)
        sys.stderr.write(idx_proc.stderr)
        return idx_proc.returncode

    out = {
        "session_id": args.session_id,
        "export": run_payload,
        "acquisition_event": {"event_id": event_id, "log_file": f"jobs/{args.session_id}/.meta/acquisition_log.jsonl"},
        "artifact_index": f"jobs/{args.session_id}/.meta/artifact_index.json",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
