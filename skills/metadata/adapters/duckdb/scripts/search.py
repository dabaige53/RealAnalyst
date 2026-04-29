#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from runtime.tableau.sqlite_store import ensure_store_ready, list_entries  # noqa: E402


def _matches(entry: dict, keyword: str) -> bool:
    haystack = " ".join(
        str(x or "")
        for x in [entry.get("source_id"), entry.get("key"), entry.get("display_name"), entry.get("description"), entry.get("category")]
    )
    return keyword.lower() in haystack.lower()


def main() -> None:
    parser = argparse.ArgumentParser(description="Search registered DuckDB sources")
    parser.add_argument("--query", required=True, help="Keyword to search")
    args = parser.parse_args()

    ensure_store_ready()
    entries = [e for e in list_entries(active_only=False) if isinstance(e, dict) and e.get("source_backend") == "duckdb"]
    items = [e for e in entries if _matches(e, args.query)]

    payload = {"query": args.query, "count": len(items), "items": items}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
