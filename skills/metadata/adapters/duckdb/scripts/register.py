#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from runtime.duckdb.register_duckdb_sources import CATALOG_PATH, _build_entry, _load_catalog  # noqa: E402
from runtime.tableau.sqlite_store import ensure_store_ready, save_entry, save_spec  # noqa: E402


def _build_targets(catalog_path: Path, *, object_names: list[str] | None) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    catalog = _load_catalog(catalog_path)
    selected = set(object_names or [])
    targets: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for obj in catalog.get("objects", []):
        if not isinstance(obj, dict):
            continue
        object_name = str(obj.get("object_name") or "")
        if selected and object_name not in selected:
            continue
        built = _build_entry(obj)
        if built:
            targets.append(built)
    return targets


def main() -> None:
    parser = argparse.ArgumentParser(description="Register DuckDB sources into unified registry.db")
    parser.add_argument("--catalog", default=str(CATALOG_PATH), help="DuckDB catalog JSON path")
    parser.add_argument("--object-name", action="append", default=[], help="Register only the specified object name")
    parser.add_argument("--all", action="store_true", help="Register all eligible objects from the catalog")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    if not args.all and not args.object_name:
        raise SystemExit("Specify --all or at least one --object-name")

    targets = _build_targets(Path(args.catalog), object_names=args.object_name or None)
    if args.object_name:
        requested = set(args.object_name)
        found = {str(entry.get("duckdb", {}).get("object_name") or "") for entry, _ in targets}
        missing = sorted(requested - found)
    else:
        missing = []

    payload = {
        "catalog": str(Path(args.catalog)),
        "count": len(targets),
        "sources": [entry.get("source_id") for entry, _ in targets],
        "entries": [entry for entry, _ in targets],
        "specs": [spec for _, spec in targets],
        "missing_object_names": missing,
        "dry_run": bool(args.dry_run),
    }

    if not args.dry_run:
        ensure_store_ready()
        for entry, spec in targets:
            save_entry(entry)
            save_spec(spec)

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
