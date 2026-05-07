#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()


def _report_script() -> Path:
    candidates = [
        WORKSPACE_DIR / "skills" / "metadata-report" / "scripts" / "generate_report.py",
        WORKSPACE_DIR / ".agents" / "skills" / "metadata-report" / "scripts" / "generate_report.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError(f"Unable to locate RA:metadata-report generate_report.py from {WORKSPACE_DIR}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compatibility wrapper for Tableau metadata reports. Delegates to RA:metadata-report."
    )
    parser.add_argument("--key", help="Legacy registry entry key; forwarded as dataset id/source id")
    parser.add_argument("--all", action="store_true", help="Generate reports for all active Tableau entries")
    parser.add_argument("--report-dir", help="Output directory for Markdown reports")
    parser.add_argument("--with-samples", action="store_true", help="Indicate this sync included sample values")
    parser.add_argument("--sync-mode", choices=["live", "dry-run"], default="live")
    parser.add_argument("--fields-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--filters-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--registry-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--export-summary", help="Optional export_summary.json path")
    parser.add_argument("--manifest", help="Optional manifest JSON path")
    return parser


def build_delegate_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(_report_script()),
        "--workspace",
        str(WORKSPACE_DIR),
        "--connector",
        "tableau",
        "--sync-mode",
        args.sync_mode,
        "--fields-step-status",
        args.fields_step_status,
        "--filters-step-status",
        args.filters_step_status,
        "--registry-step-status",
        args.registry_step_status,
    ]
    if args.report_dir:
        command.extend(["--report-dir", args.report_dir])
    if args.with_samples:
        command.append("--with-samples")
    if args.export_summary:
        command.extend(["--export-summary", args.export_summary])
    if args.manifest:
        command.extend(["--manifest", args.manifest])
    if args.key:
        command.extend(["--dataset-id", args.key])
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
