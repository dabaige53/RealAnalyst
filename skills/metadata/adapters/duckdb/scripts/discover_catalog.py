#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from runtime.duckdb.register_duckdb_sources import CATALOG_PATH, _build_entry, _load_catalog  # noqa: E402


def _match_text(value: str, keyword: str) -> bool:
    return keyword.lower() in value.lower()


def _candidate_payload(obj: dict[str, Any]) -> dict[str, Any]:
    built = _build_entry(obj)
    out = {
        "object_name": obj.get("object_name"),
        "schema": obj.get("schema"),
        "object_kind": obj.get("object_kind"),
        "business_domain": obj.get("business_domain"),
        "recommended_usage": obj.get("recommended_usage"),
        "row_count": obj.get("row_count"),
        "column_count": obj.get("column_count"),
        "time_fields": obj.get("time_fields") or [],
        "registerable": built is not None,
    }
    if built:
        entry, spec = built
        out.update(
            {
                "source_id": entry.get("source_id"),
                "display_name": entry.get("display_name"),
                "category": entry.get("category"),
                "fields_count": len(entry.get("fields") or []),
                "dimensions_count": len((spec.get("dimensions") or [])),
                "measures_count": len((spec.get("measures") or [])),
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover candidate DuckDB objects from a metadata sync catalog JSON")
    parser.add_argument("--catalog", default=str(CATALOG_PATH), help="DuckDB catalog JSON path")
    parser.add_argument("--object-name", help="Filter exact object name")
    parser.add_argument("--kind", choices=["view", "base table"], help="Filter object kind")
    parser.add_argument("--search", help="Filter by keyword on object/display/category")
    parser.add_argument("--registerable-only", action="store_true", help="Show only registerable objects")
    parser.add_argument("--output", help="Optional output JSON path")
    args = parser.parse_args()

    catalog = _load_catalog(Path(args.catalog))
    results: list[dict[str, Any]] = []
    for obj in catalog.get("objects", []):
        if not isinstance(obj, dict):
            continue
        if args.object_name and obj.get("object_name") != args.object_name:
            continue
        if args.kind and obj.get("object_kind") != args.kind:
            continue
        item = _candidate_payload(obj)
        if args.registerable_only and not item["registerable"]:
            continue
        if args.search:
            haystack = " ".join(
                str(x or "")
                for x in [item.get("object_name"), item.get("display_name"), item.get("category"), item.get("business_domain")]
            )
            if not _match_text(haystack, args.search):
                continue
        results.append(item)

    payload = {
        "catalog": str(Path(args.catalog)),
        "count": len(results),
        "items": results,
    }
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
