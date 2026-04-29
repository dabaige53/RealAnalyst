#!/usr/bin/env python3
"""Validate SQLite-backed registry entries against Tableau Server."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import requests

from _bootstrap import bootstrap_tableau_scripts_path, bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()
from runtime.tableau.sqlite_store import ensure_store_ready, list_entries

TABLEAU_SCRIPTS = bootstrap_tableau_scripts_path()
from auth import TableauAuth, get_auth  # noqa: E402  # type: ignore[import-not-found]


def check_view_exists(auth: TableauAuth, view_luid: str) -> bool:
    url = f"{auth.api_base}/views/{view_luid}"
    try:
        resp = requests.get(url, headers=auth.get_headers(), timeout=30)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def validate_entries(auth: TableauAuth, entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {"valid": [], "invalid": [], "missing_luid": [], "skipped": []}

    for entry in entries:
        key = entry.get("key", "unknown")
        status = entry.get("status", "active")
        source_type = entry.get("type", "view")

        if status != "active":
            results["skipped"].append(f"{key} (status={status})")
            continue

        if source_type == "view":
            view_luid = entry.get("tableau", {}).get("view_luid")
            if not view_luid:
                results["missing_luid"].append(str(key))
                continue

            if check_view_exists(auth, str(view_luid)):
                results["valid"].append(str(key))
            else:
                results["invalid"].append(str(key))

        elif source_type in {"domain", "dashboard"}:
            child_views_key = "views" if source_type == "domain" else "sheets"
            child_views = entry.get(child_views_key, [])
            all_valid = True
            missing = False

            for child_view in child_views:
                if not isinstance(child_view, dict):
                    continue
                view_luid = child_view.get("view_luid")
                if not view_luid:
                    missing = True
                    continue
                if not check_view_exists(auth, str(view_luid)):
                    all_valid = False

            if missing:
                results["missing_luid"].append(f"{key} (some {child_views_key})")
            elif all_valid:
                results["valid"].append(str(key))
            else:
                results["invalid"].append(str(key))

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate SQLite-backed registry entries against Tableau Server")
    parser.parse_args()

    ensure_store_ready()
    entries = [e for e in list_entries(active_only=False) if isinstance(e, dict)]

    if not entries:
        print("[Warning] No entries in registry.db")
        return

    print(f"[Validate] Checking {len(entries)} entries against Tableau...")

    auth = get_auth()
    try:
        auth.signin()
        results = validate_entries(auth, entries)

        print("\n=== Validation Results ===\n")

        if results["valid"]:
            print(f"✅ Valid ({len(results['valid'])}):")
            for key in results["valid"]:
                print(f"   - {key}")

        if results["invalid"]:
            print(f"\n❌ Invalid - view not found ({len(results['invalid'])}):")
            for key in results["invalid"]:
                print(f"   - {key}")

        if results["missing_luid"]:
            print(f"\n⚠️  Missing view_luid ({len(results['missing_luid'])}):")
            for key in results["missing_luid"]:
                print(f"   - {key}")

        if results["skipped"]:
            print(f"\n⏭️  Skipped ({len(results['skipped'])}):")
            for key in results["skipped"]:
                print(f"   - {key}")

        total = len(entries)
        valid = len(results["valid"])
        invalid = len(results["invalid"]) + len(results["missing_luid"])

        print(f"\n--- Summary: {valid}/{total} valid, {invalid} need attention ---")

        if results["invalid"] or results["missing_luid"]:
            sys.exit(1)

    finally:
        auth.signout()


if __name__ == "__main__":
    main()
