#!/usr/bin/env python3
"""Tableau export wrapper with continuous-analysis metadata write-back.

It wraps:
  skills/data-export/scripts/tableau/export_source.py

And then:
- saves the run stdout JSON into jobs/<SESSION_ID>/.meta/tableau_run_<ts>.json
- appends acquisition record into .meta/acquisition_log.jsonl (from that run JSON)
- updates .meta/artifact_index.json (best-effort)

Note: This wrapper records the run-level summary. It does not attempt to derive a full
per-file lineage beyond what export_source.py returns in its JSON output.
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


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


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


def _job_dir(session_id: str) -> Path:
    return WORKSPACE_DIR / "jobs" / session_id


def _artifact_base_dir(session_id: str, raw_output_dir: str | None) -> Path:
    if raw_output_dir and raw_output_dir.strip():
        return Path(raw_output_dir).expanduser().resolve()
    return _job_dir(session_id)


def _resolve_artifact_candidate(base_dir: Path, rel_or_path: str) -> Path:
    p = Path(rel_or_path)
    if p.is_absolute():
        return p
    candidate = (base_dir / p).resolve()
    if candidate.exists():
        return candidate
    fallback = (WORKSPACE_DIR / p).resolve()
    return fallback


def main() -> int:
    ap = argparse.ArgumentParser(description="Tableau export with metadata")
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--views", default="")
    ap.add_argument("--vf", action="append", default=[])
    ap.add_argument("--vp", action="append", default=[])
    ap.add_argument("--output-dir", default="")

    ap.add_argument("--reason", default="")
    ap.add_argument("--confirmed", action="store_true")
    ap.add_argument("--is-new-source", action="store_true")

    args = ap.parse_args()

    export_script = _resolve_skill_script("data-export", "scripts", "tableau", "export_source.py")
    cmd = [
        str(WORKSPACE_DIR / "scripts" / "py"),
        str(export_script),
        "--source-id",
        args.source_id,
        "--session-id",
        args.session_id,
    ]
    if args.views.strip():
        cmd += ["--views", args.views.strip()]
    for x in args.vf or []:
        cmd += ["--vf", x]
    for x in args.vp or []:
        cmd += ["--vp", x]
    if args.output_dir.strip():
        cmd += ["--output-dir", args.output_dir.strip()]

    artifact_base_dir = _artifact_base_dir(args.session_id, args.output_dir)

    proc = _run(cmd)
    if proc.returncode != 0:
        # Keep the exporter JSON on stdout for debugging / recovery.
        if proc.stdout:
            sys.stdout.write(proc.stdout)
            if not proc.stdout.endswith("\n"):
                sys.stdout.write("\n")
        sys.stderr.write(proc.stderr)
        return proc.returncode

    run_payload = json.loads(proc.stdout)

    # save run payload
    job = _job_dir(args.session_id)
    meta = job / ".meta"
    meta.mkdir(parents=True, exist_ok=True)
    run_path = meta / f"tableau_run_{_now_tag()}.json"
    run_path.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # log acquisition
    log_script = WORKSPACE_DIR / "scripts" / "log_acquisition.py"
    log_cmd = [
        str(WORKSPACE_DIR / "scripts" / "py"),
        str(log_script),
        "--session-id",
        args.session_id,
        "--from-tableau-run",
        str(run_path),
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

    # best-effort: index run + output artifacts
    idx_script = WORKSPACE_DIR / "scripts" / "update_artifact_index.py"

    items: list[dict[str, Any]] = []

    # 1) keep the run payload as audit
    items.append(
        {
            "path": str(run_path.relative_to(WORKSPACE_DIR)),
            "kind": "audit",
            "role": "system",
            "created_at": run_payload.get("timestamp") or _now_iso(),
            "source_backend": "tableau",
            "source_id": run_payload.get("source_id"),
            "display_name": run_payload.get("display_name"),
            "event_id": event_id,
        }
    )

    # 2) export_summary.json is the primary runtime artifact
    export_summary = job / "export_summary.json"
    if export_summary.exists():
        items.append(
            {
                "path": str(export_summary.relative_to(WORKSPACE_DIR)),
                "kind": "audit",
                "role": "system",
                "created_at": run_payload.get("timestamp") or _now_iso(),
                "source_backend": "tableau",
                "source_id": run_payload.get("source_id"),
                "event_id": event_id,
            }
        )

    # 3) optional context artifacts
    for key in ("source_context_path", "context_injection_path"):
        p = run_payload.get(key)
        if isinstance(p, str) and p:
            candidate = _resolve_artifact_candidate(artifact_base_dir, p)
            try:
                candidate.relative_to(job.resolve())
            except Exception:
                continue
            if candidate.exists():
                items.append(
                    {
                        "path": str(candidate.relative_to(WORKSPACE_DIR)),
                        "kind": "context",
                        "role": "system",
                        "created_at": run_payload.get("timestamp") or _now_iso(),
                        "source_backend": "tableau",
                        "source_id": run_payload.get("source_id"),
                        "event_id": event_id,
                        "context_key": key,
                    }
                )

    # 4) per-view artifacts
    views = run_payload.get("views")
    if isinstance(views, list):
        for v in views:
            if not isinstance(v, dict):
                continue
            view_status = v.get("status")
            view_id = v.get("id")
            view_luid = v.get("view_luid")
            resolved_params = v.get("resolved_params")

            for field, kind, role in (
                ("file_path", "raw_data", "archive"),
                ("manifest_path", "export_manifest", "system"),
                ("assertions_path", "export_assertions", "system"),
            ):
                rel = v.get(field)
                if not isinstance(rel, str) or not rel:
                    continue
                candidate = _resolve_artifact_candidate(artifact_base_dir, rel)
                try:
                    candidate.relative_to(job.resolve())
                except Exception:
                    continue
                if not candidate.exists():
                    continue
                items.append(
                    {
                        "path": str(candidate.relative_to(WORKSPACE_DIR)),
                        "kind": kind,
                        "role": role,
                        "created_at": run_payload.get("timestamp") or _now_iso(),
                        "source_backend": "tableau",
                        "source_id": run_payload.get("source_id"),
                        "display_name": run_payload.get("display_name"),
                        "event_id": event_id,
                        "view_status": view_status,
                        "view_id": view_id,
                        "view_luid": view_luid,
                        "resolved_params": resolved_params,
                    }
                )

    idx_cmd = [
        str(WORKSPACE_DIR / "scripts" / "py"),
        str(idx_script),
        "--session-id",
        args.session_id,
    ]
    for it in items:
        idx_cmd += ["--item", json.dumps(it, ensure_ascii=False)]

    idx_proc = _run(idx_cmd)
    if idx_proc.returncode != 0:
        sys.stderr.write(idx_proc.stdout)
        sys.stderr.write(idx_proc.stderr)
        return idx_proc.returncode

    out = {
        "session_id": args.session_id,
        "run_summary": run_payload,
        "run_saved": str(run_path.relative_to(WORKSPACE_DIR)),
        "acquisition_event": {"event_id": event_id, "log_file": f"jobs/{args.session_id}/.meta/acquisition_log.jsonl"},
        "artifact_index": f"jobs/{args.session_id}/.meta/artifact_index.json",
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
