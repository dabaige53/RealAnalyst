#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from runtime.tableau.sqlite_store import list_entries  # noqa: E402


def _report_script() -> Path:
    candidates = [
        WORKSPACE_DIR / "skills" / "metadata-report" / "scripts" / "generate_report.py",
        WORKSPACE_DIR / ".agents" / "skills" / "metadata-report" / "scripts" / "generate_report.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError(f"Unable to locate RA:metadata-report generate_report.py from {WORKSPACE_DIR}")


def _source_id_for_key(key: str) -> str:
    for entry in list_entries(active_only=False):
        if isinstance(entry, dict) and entry.get("key") == key:
            return str(entry.get("source_id") or key)
    return key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compatibility wrapper for DuckDB metadata reports. Delegates to RA:metadata-report."
    )
    parser.add_argument("--key", help="Legacy registry entry key; forwarded as dataset id/source id")
    parser.add_argument("--all", action="store_true", help="Generate reports for all active DuckDB entries")
    parser.add_argument("--report-dir", help="Output directory for Markdown reports")
    parser.add_argument("--sync-mode", choices=["live", "dry-run"], default="live")
    parser.add_argument("--register-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--registry-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--validate-step-status", choices=["success", "failed", "skipped"], default="success")
    return parser


def build_delegate_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(_report_script()),
        "--workspace",
        str(WORKSPACE_DIR),
        "--connector",
        "duckdb",
        "--sync-mode",
        args.sync_mode,
        "--register-step-status",
        args.register_step_status,
        "--registry-step-status",
        args.registry_step_status,
        "--validate-step-status",
        args.validate_step_status,
    ]
    if args.report_dir:
        command.extend(["--report-dir", args.report_dir])
    if args.key:
        command.extend(["--dataset-id", _source_id_for_key(args.key)])
    elif args.all:
        command.append("--all")
    return command


def main() -> None:
    args = build_parser().parse_args()
    if not args.key and not args.all:
        print("[Error] Specify --key KEY or --all")
        raise SystemExit(2)
    raise SystemExit(subprocess.run(build_delegate_command(args)).returncode)


if __name__ == "__main__":
    main()
