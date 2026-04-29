#!/usr/bin/env python3
"""Discover Tableau views and dashboards, output candidate list for registration."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from _bootstrap import bootstrap_tableau_scripts_path

TABLEAU_SCRIPTS = bootstrap_tableau_scripts_path()

from auth import TableauAuth, get_auth  # noqa: E402  # type: ignore[import-not-found]


def discover_views(auth: TableauAuth, workbook_filter: str | None = None) -> list[dict[str, Any]]:
    url = f"{auth.api_base}/views?pageSize=1000"
    resp = requests.get(url, headers=auth.get_headers(), timeout=60)
    resp.raise_for_status()
    views = resp.json().get("views", {}).get("view", [])

    if workbook_filter:
        views = [
            v
            for v in views
            if workbook_filter.lower() in v.get("workbook", {}).get("name", "").lower()
        ]

    return views


def build_candidate(view: dict[str, Any], category: str = "uncategorized") -> dict[str, Any]:
    workbook = view.get("workbook", {})
    view_url_name = view.get("viewUrlName", "unknown")
    key = f"{category}.{view_url_name}".lower().replace(" ", "_")

    return {
        "key": key,
        "type": "view",
        "status": "disabled",
        "display_name": view.get("name", ""),
        "description": "",
        "category": category,
        "tableau": {
            "workbook_name": workbook.get("name", ""),
            "workbook_luid": workbook.get("id", ""),
            "view_luid": view.get("id", ""),
            "view_name": view.get("name", ""),
            "content_url": view.get("contentUrl", ""),
        },
        "discovered_at": datetime.now(timezone.utc).isoformat(),
    }


def format_table(candidates: list[dict[str, Any]]) -> str:
    lines = ["", "=== Discovered Views ===", ""]
    header = f"{'KEY':<40} {'DISPLAY_NAME':<30} {'WORKBOOK':<20} {'VIEW_LUID':<36}"
    lines.append(header)
    lines.append("-" * 130)

    for c in candidates:
        key = c["key"][:40]
        display_name = c["display_name"][:30]
        workbook_name = c["tableau"]["workbook_name"][:20]
        view_luid = c["tableau"]["view_luid"][:36]
        lines.append(f"{key:<40} {display_name:<30} {workbook_name:<20} {view_luid:<36}")

    lines.extend(
        [
            "",
            f"Total: {len(candidates)} views",
            "",
            "To register a view, run:",
            "  python skills/metadata/adapters/tableau/scripts/register.py <view_luid>",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Tableau views and dashboards")
    parser.add_argument("--workbook", help="Filter by workbook name")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    parser.add_argument("--format", choices=["json", "table"], default="table")
    args = parser.parse_args()

    auth = get_auth()
    try:
        # Signin already prints to stderr if we update auth.py
        auth.signin()
        print("[Tableau-Sync] Discovering views...", file=sys.stderr)

        views = discover_views(auth, args.workbook)
        candidates = [build_candidate(v) for v in views]

        print(f"[Tableau-Sync] Found {len(candidates)} views", file=sys.stderr)

        if args.format == "json":
            output = json.dumps(candidates, ensure_ascii=False, indent=2)
        else:
            output = format_table(candidates)

        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(f"[Tableau-Sync] Written to {args.output}", file=sys.stderr)
        else:
            print(output)

    finally:
        auth.signout()


if __name__ == "__main__":
    main()
