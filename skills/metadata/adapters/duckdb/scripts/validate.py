#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from runtime.tableau.sqlite_store import ensure_store_ready, list_entries, load_spec_by_entry_key  # noqa: E402


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _validate_entry(entry: dict[str, Any]) -> dict[str, Any]:
    key = str(entry.get("key") or "")
    spec = load_spec_by_entry_key(key) or {}
    errors: list[str] = []

    if entry.get("source_backend") != "duckdb":
        errors.append("source_backend must equal duckdb")
    if entry.get("type") not in {"duckdb_view", "duckdb_table"}:
        errors.append("type must be duckdb_view or duckdb_table")
    if entry.get("status") != "active":
        errors.append("status must be active")

    duckdb_meta = entry.get("duckdb") if isinstance(entry.get("duckdb"), dict) else {}
    if not duckdb_meta.get("db_path"):
        errors.append("duckdb.db_path is required")
    if not duckdb_meta.get("object_name"):
        errors.append("duckdb.object_name is required")
    if not _safe_list(entry.get("fields")):
        errors.append("entry.fields is empty")

    if not spec:
        errors.append("spec is missing")
    else:
        if not (_safe_list(spec.get("fields")) or _safe_list(spec.get("dimensions")) or _safe_list(spec.get("measures"))):
            errors.append("spec has no usable fields/dimensions/measures")

    return {
        "key": key,
        "source_id": entry.get("source_id"),
        "valid": not errors,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate registered DuckDB sources")
    parser.add_argument("--key", help="Validate a single DuckDB entry by key")
    parser.add_argument("--all", action="store_true", help="Validate all DuckDB entries")
    args = parser.parse_args()

    if not args.key and not args.all:
        print("[Error] Specify --key KEY or --all", file=sys.stderr)
        raise SystemExit(2)

    ensure_store_ready()
    entries = [e for e in list_entries(active_only=False) if isinstance(e, dict) and e.get("source_backend") == "duckdb"]
    targets = [e for e in entries if e.get("key") == args.key] if args.key else entries
    results = [_validate_entry(entry) for entry in targets]
    payload = {
        "count": len(results),
        "valid_count": sum(1 for x in results if x["valid"]),
        "invalid_count": sum(1 for x in results if not x["valid"]),
        "results": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["invalid_count"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
