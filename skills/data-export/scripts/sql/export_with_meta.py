#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def find_workspace_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        has_skills = (candidate / "skills").is_dir() or (candidate / ".agents" / "skills").is_dir()
        if (candidate / "runtime").is_dir() and has_skills:
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE_DIR = find_workspace_root(Path(__file__).resolve())


def resolve_skill_script(*parts: str) -> Path:
    candidates = [
        WORKSPACE_DIR / "skills" / Path(*parts),
        WORKSPACE_DIR / ".agents" / "skills" / Path(*parts),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True)


def build_parser(connector: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"{connector} export with metadata")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output-name", required=True)
    parser.add_argument("--select")
    parser.add_argument("--filter", action="append", default=[])
    parser.add_argument("--date-range", action="append", default=[])
    parser.add_argument("--group-by")
    parser.add_argument("--aggregate", action="append", default=[])
    parser.add_argument("--order-by", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--reason", default="")
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--is-new-source", action="store_true")
    return parser


def main(connector: str) -> int:
    args = build_parser(connector).parse_args()
    export_script = resolve_skill_script("data-export", "scripts", connector, f"export_{connector}_source.py")
    command = [
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
        command += ["--select", args.select]
    for value in args.filter:
        command += ["--filter", value]
    for value in args.date_range:
        command += ["--date-range", value]
    if args.group_by:
        command += ["--group-by", args.group_by]
    for value in args.aggregate:
        command += ["--aggregate", value]
    for value in args.order_by:
        command += ["--order-by", value]
    if args.limit is not None:
        command += ["--limit", str(args.limit)]

    proc = run(command)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return proc.returncode
    run_payload = json.loads(proc.stdout)
    summary_file = run_payload.get("summary_file")
    if not isinstance(summary_file, str) or not summary_file:
        raise SystemExit("missing summary_file from export")
    summary_path = Path(summary_file)

    log_command = [
        str(WORKSPACE_DIR / "scripts" / "py"),
        str(WORKSPACE_DIR / "scripts" / "log_acquisition.py"),
        "--session-id",
        args.session_id,
        "--from-sql-summary",
        str(summary_path),
        "--reason",
        args.reason,
    ]
    if args.confirmed:
        log_command.append("--confirmed")
    if args.is_new_source:
        log_command.append("--is-new-source")
    log_proc = run(log_command)
    if log_proc.returncode != 0:
        sys.stderr.write(log_proc.stdout)
        sys.stderr.write(log_proc.stderr)
        return log_proc.returncode
    log_payload = json.loads(log_proc.stdout)
    event_id = log_payload.get("event_id")

    index_command = [
        str(WORKSPACE_DIR / "scripts" / "py"),
        str(WORKSPACE_DIR / "scripts" / "update_artifact_index.py"),
        "--session-id",
        args.session_id,
        "--from-sql-summary",
        str(summary_path),
    ]
    if isinstance(event_id, str) and event_id:
        index_command += ["--event-id", event_id]
    index_proc = run(index_command)
    if index_proc.returncode != 0:
        sys.stderr.write(index_proc.stdout)
        sys.stderr.write(index_proc.stderr)
        return index_proc.returncode

    context_available = False
    context_dest: str | None = None
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    dataset_id = summary.get("dataset_id") or summary.get("source_id", "")
    if dataset_id:
        source_context = WORKSPACE_DIR / "metadata" / "osi" / str(dataset_id) / "context.md"
        if source_context.exists():
            job_dir = WORKSPACE_DIR / "jobs" / args.session_id
            job_dir.mkdir(parents=True, exist_ok=True)
            dest = job_dir / "context_injection.md"
            shutil.copy2(source_context, dest)
            context_available = True
            context_dest = str(dest)

    out = {
        "session_id": args.session_id,
        "export": run_payload,
        "acquisition_event": {"event_id": event_id, "log_file": f"jobs/{args.session_id}/.meta/acquisition_log.jsonl"},
        "artifact_index": f"jobs/{args.session_id}/.meta/artifact_index.json",
        "context_injection": {"available": context_available, "path": context_dest},
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0
