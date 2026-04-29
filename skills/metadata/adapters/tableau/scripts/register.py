#!/usr/bin/env python3
"""Register a Tableau view to SQLite registry store (runtime/registry.db)."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests

from _bootstrap import bootstrap_tableau_scripts_path, bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()
from runtime.tableau.sqlite_store import ensure_store_ready, list_entries, save_entry, save_spec

TABLEAU_SCRIPTS = bootstrap_tableau_scripts_path()
from auth import TableauAuth, get_auth  # noqa: E402  # type: ignore[import-not-found]


def get_view_info(auth: TableauAuth, view_luid: str) -> dict[str, Any] | None:
    url = f"{auth.api_base}/views/{view_luid}"
    resp = requests.get(url, headers=auth.get_headers(), timeout=60)
    if resp.status_code != 200:
        return None
    return resp.json().get("view", {})


def build_entry(view: dict[str, Any], category: str, display_name: str | None) -> dict[str, Any]:
    workbook = view.get("workbook", {})
    view_url_name = str(view.get("viewUrlName", "unknown"))
    content_url = view.get("contentUrl", "")
    if not isinstance(content_url, str) or not content_url.strip():
        raise ValueError("Tableau view payload missing required contentUrl")

    key = f"{category}.{view_url_name}".lower().replace(" ", "_")
    return {
        "key": key,
        "source_id": f"tableau.{key}",
        "type": "view",
        "status": "active",
        "display_name": display_name or view.get("name", ""),
        "description": "",
        "category": category,
        "tags": [],
        "tableau": {
            "workbook_id": workbook.get("id", ""),
            "workbook_name": workbook.get("name", ""),
            "view_luid": view.get("id", ""),
            "view_name": view.get("name", ""),
            "content_url": content_url.strip(),
        },
        "semantics": {
            "grain": [],
            "primary_dimensions": [],
            "available_metrics": [],
            "suitable_for": [],
            "not_suitable_for": [],
        },
        "agent": {
            "default_template": "executive_onepage",
            "suggested_questions": [],
            "require_verifier": True,
        },
    }


def build_initial_spec(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_key": entry["key"],
        "display_name": entry.get("display_name", entry["key"]),
        "updated": None,
        "filters": [],
        "dimensions": [],
        "measures": [],
        "parameters": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a Tableau view to registry.db")
    parser.add_argument("view_luid", help="Tableau view LUID")
    parser.add_argument("--category", default="uncategorized", help="Category (e.g., market, sales)")
    parser.add_argument("--display-name", help="Display name (default: from Tableau)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be added without saving")
    args = parser.parse_args()

    ensure_store_ready()

    auth = get_auth()
    try:
        auth.signin()

        view = get_view_info(auth, args.view_luid)
        if not view:
            print(f"[Error] View not found: {args.view_luid}", file=sys.stderr)
            raise SystemExit(1)

        print(f"[Tableau-Sync] Found view: {view.get('name')}")
        entry = build_entry(view, args.category, args.display_name)

        existing_keys = {e.get("key") for e in list_entries(active_only=False) if isinstance(e, dict)}
        if entry["key"] in existing_keys:
            print(f"[Warning] Entry already exists: {entry['key']}")
            print("[Hint] Use --category to change the key")
            raise SystemExit(1)

        if args.dry_run:
            print("\n[Dry-run] Would add entry:")
            print(json.dumps(entry, ensure_ascii=False, indent=2))
            print("\n[Dry-run] Would initialize spec:")
            print(json.dumps(build_initial_spec(entry), ensure_ascii=False, indent=2))
            return

        save_entry(entry)
        save_spec(build_initial_spec(entry))

        print(f"\n✅ Registered: {entry['key']}")
        print("\nNext steps:")
        print("  1. Update entry description / semantics in registry.db via your maintenance flow")
        print(f"  2. Run: ./scripts/py skills/metadata/adapters/tableau/scripts/sync_all.py --key {entry['key']}")

    finally:
        auth.signout()


if __name__ == "__main__":
    main()
