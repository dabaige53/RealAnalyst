#!/usr/bin/env python3
"""Sync registry semantics from SQLite-backed per-source specs."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()
from runtime.tableau.sqlite_store import (
    ensure_store_ready,
    list_entries,
    load_spec_by_entry_key,
    save_entry,
)


def _names_from_spec_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for v in value:
        if isinstance(v, dict) and isinstance(v.get("name"), str) and v.get("name"):
            out.append(v["name"])
        elif isinstance(v, str) and v:
            out.append(v)
    seen: set[str] = set()
    uniq: list[str] = []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


def sync_entry(entry: dict[str, Any], dry_run: bool) -> bool:
    key = entry.get("key")
    if not isinstance(key, str) or not key:
        return False

    spec = load_spec_by_entry_key(key) or {}
    dims = _names_from_spec_list(spec.get("dimensions"))
    meas = _names_from_spec_list(spec.get("measures"))
    if not dims and not meas:
        return False

    semantics = entry.get("semantics")
    if not isinstance(semantics, dict):
        semantics = {}

    old_dims = _names_from_spec_list(semantics.get("primary_dimensions"))
    old_meas = _names_from_spec_list(semantics.get("available_metrics"))
    changed = old_dims != dims or old_meas != meas
    if not changed:
        return False

    if dry_run:
        return True

    semantics["primary_dimensions"] = dims
    semantics["available_metrics"] = meas
    entry["semantics"] = semantics
    save_entry(entry)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync registry.db semantics from per-source specs")
    parser.add_argument("--key", help="Sync a single entry by key")
    parser.add_argument("--all", action="store_true", help="Sync all entries")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    if not args.key and not args.all:
        print("[Error] Specify --key KEY or --all", file=sys.stderr)
        raise SystemExit(2)

    ensure_store_ready()
    entries = list_entries(active_only=False)
    if args.key:
        targets = [e for e in entries if isinstance(e, dict) and e.get("key") == args.key]
    else:
        targets = [e for e in entries if isinstance(e, dict)]

    changed = 0
    for entry in targets:
        if sync_entry(entry, dry_run=args.dry_run):
            changed += 1

    if args.dry_run:
        print(f"[DRY] Would update semantics for {changed} entries")
        return

    if changed == 0:
        print("[OK] No semantic changes detected")
        return

    print(f"[OK] Updated semantics for {changed} entries in registry.db")


if __name__ == "__main__":
    main()
