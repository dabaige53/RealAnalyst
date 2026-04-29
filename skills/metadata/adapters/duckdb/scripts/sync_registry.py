#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from runtime.tableau.sqlite_store import ensure_store_ready, list_entries, load_spec_by_entry_key, save_entry  # noqa: E402


def _safe_list_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [x for x in value if isinstance(x, dict)]


def _safe_list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x) for x in value if isinstance(x, str) and x]


def _updated_entry(entry: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    semantics = dict(entry.get("semantics") or {})
    semantics["grain"] = _safe_list_str(spec.get("grain"))
    semantics["time_fields"] = _safe_list_str(spec.get("time_fields"))
    semantics["primary_dimensions"] = [str(x.get("name")) for x in _safe_list_dicts(spec.get("dimensions")) if x.get("name")]
    semantics["available_metrics"] = [str(x.get("name")) for x in _safe_list_dicts(spec.get("measures")) if x.get("name")]
    semantics["suitable_for"] = _safe_list_str(spec.get("recommended_questions")) or semantics.get("suitable_for", [])
    if spec.get("limitations"):
        semantics["not_suitable_for"] = _safe_list_str(spec.get("limitations"))

    updated = dict(entry)
    updated["fields"] = _safe_list_str(spec.get("fields")) or updated.get("fields", [])
    updated["display_name"] = spec.get("display_name") or updated.get("display_name")
    updated["semantics"] = semantics
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync DuckDB registry semantics from per-source specs")
    parser.add_argument("--key", help="Sync a single entry by key")
    parser.add_argument("--all", action="store_true", help="Sync all DuckDB entries")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    if not args.key and not args.all:
        print("[Error] Specify --key KEY or --all", file=sys.stderr)
        raise SystemExit(2)

    ensure_store_ready()
    entries = [e for e in list_entries(active_only=False) if isinstance(e, dict) and e.get("source_backend") == "duckdb"]
    targets = [e for e in entries if e.get("key") == args.key] if args.key else entries

    results: list[dict[str, Any]] = []
    for entry in targets:
        key = str(entry.get("key") or "")
        spec = load_spec_by_entry_key(key) or {}
        if not spec:
            results.append({"key": key, "status": "missing_spec"})
            continue
        updated = _updated_entry(entry, spec)
        if not args.dry_run:
            save_entry(updated)
        results.append(
            {
                "key": key,
                "source_id": updated.get("source_id"),
                "status": "updated" if not args.dry_run else "preview",
                "primary_dimensions": len((updated.get("semantics") or {}).get("primary_dimensions") or []),
                "available_metrics": len((updated.get("semantics") or {}).get("available_metrics") or []),
                "time_fields": len((updated.get("semantics") or {}).get("time_fields") or []),
            }
        )

    print(json.dumps({"count": len(results), "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
