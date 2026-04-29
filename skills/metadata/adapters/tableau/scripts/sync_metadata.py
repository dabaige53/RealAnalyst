#!/usr/bin/env python3
"""Compatibility wrapper for legacy sync_metadata entrypoint.

Historical flows called this script as a one-shot Tableau metadata sync.
Current runtime stores registry/specs in SQLite, so this wrapper now delegates
in order to:
- sync_fields.py
- sync_filters.py
- sync_registry.py

This keeps older automation usable while moving the actual write path to the
latest registry.db / per-source spec chain.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()
PY = WORKSPACE_DIR / "scripts" / "py"
SCRIPT_DIR = Path(__file__).resolve().parent


def _run(script_name: str, extra_args: list[str]) -> None:
    cmd = [str(PY), str(SCRIPT_DIR / script_name), *extra_args]
    result = subprocess.run(cmd, cwd=WORKSPACE_DIR)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Legacy wrapper for full Tableau metadata sync")
    parser.add_argument("--key", help="Sync a single entry by key")
    parser.add_argument("--all", action="store_true", help="Sync all entries")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    if not args.key and not args.all:
        print("[Error] Specify --key KEY or --all", file=sys.stderr)
        raise SystemExit(2)

    scope_args: list[str] = ["--key", args.key] if args.key else ["--all"]
    if args.dry_run:
        scope_args.append("--dry-run")

    print("[Compat] sync_metadata.py -> sync_fields.py + sync_filters.py + sync_registry.py")
    _run("sync_fields.py", scope_args)
    _run("sync_filters.py", scope_args)
    _run("sync_registry.py", scope_args)
    print("[OK] Legacy sync_metadata flow completed on latest registry.db pipeline")


if __name__ == "__main__":
    main()
