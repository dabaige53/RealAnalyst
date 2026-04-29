#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()
PY = WORKSPACE_DIR / "scripts" / "py"
SCRIPT_DIR = Path(__file__).resolve().parent


def _run(script_name: str, args: list[str]) -> tuple[bool, str]:
    cmd = [str(PY), str(SCRIPT_DIR / script_name), *args]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified DuckDB sync: register + sync_registry + validate + report")
    parser.add_argument("--catalog", default="", help="DuckDB catalog JSON path")
    parser.add_argument("--object-name", action="append", default=[], help="Sync only one or more object names")
    parser.add_argument("--all", action="store_true", help="Sync all eligible objects")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument(
        "--report-dir",
        help="Markdown report output directory (default: metadata/sync/duckdb/reports)",
    )
    args = parser.parse_args()

    if not args.all and not args.object_name:
        print("[Error] Specify --all or at least one --object-name", file=sys.stderr)
        raise SystemExit(2)

    register_args: list[str] = []
    if args.catalog:
        register_args += ["--catalog", args.catalog]
    if args.all:
        register_args.append("--all")
    for name in args.object_name:
        register_args += ["--object-name", name]
    if args.dry_run:
        register_args.append("--dry-run")

    ok_register, out_register = _run("register.py", register_args)
    register_status = "success" if ok_register else "failed"
    print(out_register, end="" if out_register.endswith("\n") or not out_register else "\n")
    if not ok_register:
        raise SystemExit(1)

    sync_args = ["--all"]
    if args.dry_run:
        sync_args.append("--dry-run")
    ok_sync, out_sync = _run("sync_registry.py", sync_args)
    registry_status = "success" if ok_sync else "failed"
    print(out_sync, end="" if out_sync.endswith("\n") or not out_sync else "\n")
    if not ok_sync:
        raise SystemExit(1)

    validate_args = ["--all"]
    ok_validate, out_validate = _run("validate.py", validate_args)
    validate_status = "success" if ok_validate else "failed"
    print(out_validate, end="" if out_validate.endswith("\n") or not out_validate else "\n")
    if not ok_validate:
        raise SystemExit(1)

    if not args.dry_run:
        report_args: list[str] = []
        if args.all:
            report_args.append("--all")
        else:
            for name in args.object_name:
                key = f"duckdb.example.{name.lower()}"
                ok_report, out_report = _run(
                    "generate_sync_report.py",
                    [
                        "--key",
                        key,
                        "--sync-mode",
                        "live",
                        "--register-step-status",
                        register_status,
                        "--registry-step-status",
                        registry_status,
                        "--validate-step-status",
                        validate_status,
                        *(["--report-dir", args.report_dir] if args.report_dir else []),
                    ],
                )
                print(out_report, end="" if out_report.endswith("\n") or not out_report else "\n")
                if not ok_report:
                    raise SystemExit(1)
            return
        report_args += [
            "--sync-mode",
            "live",
            "--register-step-status",
            register_status,
            "--registry-step-status",
            registry_status,
            "--validate-step-status",
            validate_status,
        ]
        if args.report_dir:
            report_args += ["--report-dir", args.report_dir]
        ok_report, out_report = _run("generate_sync_report.py", report_args)
        print(out_report, end="" if out_report.endswith("\n") or not out_report else "\n")
        if not ok_report:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
