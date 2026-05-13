#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _common import make_refine_id, resolve_workspace_path, workspace_path


SCRIPT_DIR = Path(__file__).resolve().parent


def run_step(command: list[str], *, cwd: Path) -> dict[str, object]:
    proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    return {
        "command": " ".join(command),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a guided metadata-report gap resolution workflow from real profiling evidence.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--refine-id", default="")
    parser.add_argument("--data-csv", default="", help="Formal CSV exported from the registered source.")
    parser.add_argument("--profile-json", default="", help="Optional existing profile JSON.")
    parser.add_argument("--max-rows", type=int, default=5000)
    parser.add_argument("--run-loop", action="store_true", help="Run validate, index, sync-registry --dry-run, and metadata-report after the reference pack is built.")
    args = parser.parse_args()

    workspace = workspace_path(args.workspace)
    refine_id = args.refine_id.strip() or make_refine_id(args.session_id or args.dataset_id)
    steps: list[dict[str, object]] = []
    data_csv = resolve_workspace_path(workspace, args.data_csv) if args.data_csv else None

    if data_csv:
        steps.append(
            run_step(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "probe_data.py"),
                    "--workspace",
                    str(workspace),
                    "--dataset-id",
                    args.dataset_id,
                    "--refine-id",
                    refine_id,
                    "--data-csv",
                    str(data_csv),
                    "--max-rows",
                    str(args.max_rows),
                ],
                cwd=workspace,
            )
        )
        if steps[-1]["returncode"] != 0:
            print(json.dumps({"success": False, "refine_id": refine_id, "steps": steps}, ensure_ascii=False, indent=2))
            return int(steps[-1]["returncode"])

    pack_command = [
        sys.executable,
        str(SCRIPT_DIR / "build_reference_pack.py"),
        "--workspace",
        str(workspace),
        "--dataset-id",
        args.dataset_id,
        "--refine-id",
        refine_id,
    ]
    if args.session_id:
        pack_command += ["--session-id", args.session_id]
    if data_csv:
        pack_command += ["--data-csv", str(data_csv), "--probe-dir", str(workspace / "runtime" / "metadata-refine" / refine_id)]
    if args.profile_json:
        pack_command += ["--profile-json", args.profile_json]
    steps.append(run_step(pack_command, cwd=workspace))
    if steps[-1]["returncode"] != 0:
        print(json.dumps({"success": False, "refine_id": refine_id, "steps": steps}, ensure_ascii=False, indent=2))
        return int(steps[-1]["returncode"])

    if args.run_loop:
        metadata_py = workspace / "skills" / "metadata" / "scripts" / "metadata.py"
        report_py = workspace / "skills" / "metadata-report" / "scripts" / "generate_report.py"
        if not metadata_py.exists():
            metadata_py = workspace / ".agents" / "skills" / "metadata" / "scripts" / "metadata.py"
        if not report_py.exists():
            report_py = workspace / ".agents" / "skills" / "metadata-report" / "scripts" / "generate_report.py"
        loop_commands = [
            [sys.executable, str(metadata_py), "--workspace", str(workspace), "validate"],
            [sys.executable, str(metadata_py), "--workspace", str(workspace), "index"],
            [sys.executable, str(metadata_py), "--workspace", str(workspace), "sync-registry", "--dataset-id", args.dataset_id, "--dry-run"],
            [sys.executable, str(report_py), "--workspace", str(workspace), "--dataset-id", args.dataset_id],
        ]
        for command in loop_commands:
            steps.append(run_step(command, cwd=workspace))
            if steps[-1]["returncode"] != 0:
                break

    print(
        json.dumps(
            {
                "success": all(step["returncode"] == 0 for step in steps),
                "refine_id": refine_id,
                "output_dir": str(workspace / "runtime" / "metadata-refine" / refine_id),
                "suggestion_status": "candidate_requires_human_review",
                "steps": steps,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(step["returncode"] == 0 for step in steps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
