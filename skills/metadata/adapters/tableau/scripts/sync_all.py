#!/usr/bin/env python3
"""Unified sync script: fields + filters + registry in one command.

This script combines sync_fields.py, sync_filters.py, and sync_registry.py
into a single convenient command.

Usage:
    python sync_all.py --all                    # Sync all active entries
    python sync_all.py --key sales.agent        # Sync single entry
    python sync_all.py --all --with-samples     # Include sample values
    python sync_all.py --all --dry-run          # Preview without saving
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def run_script(script_name: str, args: list[str]) -> tuple[bool, str]:
    """Run a sync script and return (success, output)."""
    script_path = SCRIPT_DIR / script_name
    cmd = [sys.executable, str(script_path)] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"[TIMEOUT] {script_name} exceeded 5 minutes"
    except Exception as e:
        return False, f"[ERROR] {script_name}: {e}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified sync: fields + filters + registry")
    parser.add_argument("--key", help="Sync specific entry by key")
    parser.add_argument("--all", action="store_true", help="Sync all active entries")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    parser.add_argument(
        "--with-samples", action="store_true", help="Fetch sample_values for filters"
    )
    parser.add_argument(
        "--skip-registry",
        action="store_true",
        help="Skip sync_registry step (semantics writeback)",
    )
    args = parser.parse_args()

    if not args.key and not args.all:
        print("[Error] Specify --key KEY or --all", file=sys.stderr)
        raise SystemExit(2)

    print("=" * 60)
    print("Tableau Unified Sync")
    print("=" * 60)

    overall_success = True

    # Build common args
    common_args: list[str] = []
    if args.key:
        common_args.extend(["--key", args.key])
    if args.all:
        common_args.append("--all")
    if args.dry_run:
        common_args.append("--dry-run")

    # Step 1: sync_fields.py
    print("\n[1/3] Syncing fields (dimensions/measures)...")
    fields_args = common_args.copy()
    if args.with_samples:
        fields_args.append("--with-samples")
    success, output = run_script("sync_fields.py", fields_args)
    fields_status = "success" if success else "failed"
    # Print only key lines
    for line in output.splitlines():
        if any(
            x in line
            for x in ["[SYNC]", "[SAVED]", "Dimensions:", "Measures:", "[ERROR]", "[WARN]"]
        ):
            print(f"  {line}")
    if not success:
        print("  [FAILED] sync_fields.py")
        overall_success = False
        # Continue anyway, some entries might have worked

    # Step 2: sync_filters.py
    print("\n[2/3] Syncing filters (filters/parameters)...")
    filters_args = common_args.copy()
    if args.with_samples:
        filters_args.append("--with-samples")
    success, output = run_script("sync_filters.py", filters_args)
    filters_status = "success" if success else "failed"
    for line in output.splitlines():
        if any(x in line for x in ["[SYNC]", "[OK]", "[ERROR]", "[WARN]"]):
            print(f"  {line}")
    if not success:
        print("  [FAILED] sync_filters.py")
        overall_success = False

    # Step 3: sync_registry.py (unless skipped)
    if not args.skip_registry:
        print("\n[3/3] Syncing registry (semantics writeback)...")
        registry_args = common_args.copy()
        success, output = run_script("sync_registry.py", registry_args)
        registry_status = "success" if success else "failed"
        for line in output.splitlines():
            if any(x in line for x in ["[OK]", "[DRY]", "[ERROR]"]):
                print(f"  {line}")
        if not success:
            print("  [FAILED] sync_registry.py")
            overall_success = False
    else:
        registry_status = "skipped"
        print("\n[3/3] Skipped sync_registry (--skip-registry)")

    if not args.dry_run:
        print("\n[4/4] Metadata sync complete.")
        print(
            "  Next step: use RA:metadata-report "
            "(`skills/metadata-report/scripts/generate_report.py`) to generate Markdown reports."
        )
        print(
            f"  Step status: fields={fields_status}, filters={filters_status}, registry={registry_status}"
        )
    else:
        print("\n[4/4] Skipped Markdown report instruction (--dry-run)")

    print("\n" + "=" * 60)
    print("Sync complete!" if overall_success else "Sync completed with errors")
    print("=" * 60)
    raise SystemExit(0 if overall_success else 1)


if __name__ == "__main__":
    main()
