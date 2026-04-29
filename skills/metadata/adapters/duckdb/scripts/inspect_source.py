#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from runtime.tableau.sqlite_store import ensure_store_ready, list_entries, load_spec_for_entry  # noqa: E402


def _resolve_source(query: str) -> tuple[dict | None, list[dict]]:
    entries = [e for e in list_entries(active_only=False) if isinstance(e, dict)]

    for field in ("display_name", "source_id", "key"):
        for entry in entries:
            if entry.get(field) == query:
                return entry, []

    query_norm = query.strip().lower()
    suggestions: list[dict] = []
    for entry in entries:
        haystack = " ".join(str(entry.get(field) or "") for field in ("display_name", "source_id", "key"))
        if query_norm and query_norm in haystack.lower():
            suggestions.append(entry)
    return None, suggestions


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a DuckDB source from registry.db")
    parser.add_argument("--source", required=True, help="source_id, key, or display_name")
    args = parser.parse_args()

    ensure_store_ready()
    source, suggestions = _resolve_source(args.source)
    if not source:
        print(json.dumps({"found": False, "suggestions": suggestions}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    if source.get("source_backend") != "duckdb":
        print(json.dumps({"found": True, "error": "source is not duckdb", "entry": source}, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    spec = load_spec_for_entry(source) or {}
    payload = {
        "found": True,
        "entry": source,
        "spec": spec,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
