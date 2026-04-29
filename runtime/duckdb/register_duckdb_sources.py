#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_DIR = Path(__file__).resolve().parents[2]
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from runtime.tableau.sqlite_store import save_entry, save_spec


CATALOG_PATH = WORKSPACE_DIR / "metadata" / "sync" / "duckdb" / "catalog.example.json"
DB_RELATIVE_PATH = "examples/data/demo_retail.duckdb"
EXCLUDE_PREFIXES = ("TEMP_", "ToDrop_")


def _load_catalog(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _make_key(object_name: str) -> str:
    return f"duckdb.example.{object_name.lower()}"


def _dimension_names(columns: list[dict[str, str]]) -> list[str]:
    out: list[str] = []
    for col in columns:
        col_type = str(col.get("type", "")).upper()
        name = str(col.get("name", ""))
        if any(x in col_type for x in ["INT", "DOUBLE", "REAL", "DECIMAL", "FLOAT", "DATE", "TIME"]):
            continue
        out.append(name)
    return out[:20]


def _measure_names(columns: list[dict[str, str]]) -> list[str]:
    out: list[str] = []
    for col in columns:
        col_type = str(col.get("type", "")).upper()
        name = str(col.get("name", ""))
        if any(x in col_type for x in ["INT", "DOUBLE", "REAL", "DECIMAL", "FLOAT"]):
            out.append(name)
    return out[:30]


def _build_entry(obj: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    object_name = str(obj["object_name"])
    if object_name.startswith(EXCLUDE_PREFIXES):
        return None

    columns = obj.get("columns", [])
    fields = [c["name"] for c in columns if isinstance(c, dict) and c.get("name")]
    measures = _measure_names(columns)
    dimensions = _dimension_names(columns)
    time_fields = obj.get("time_fields", [])
    category = str(obj.get("business_domain") or "dataset")
    display_name = str(obj.get("display_name") or object_name.replace("_", " ").title())
    description = str(obj.get("description") or f"Example DuckDB object for {display_name}.")
    grain = obj.get("grain") or [fields[0]] if fields else []
    suitable_for = obj.get("suitable_for") or ["example analysis", "metadata onboarding"]
    not_suitable_for = obj.get("not_suitable_for") or ["production analysis without review"]
    limitations = obj.get("limitations") or ["Example metadata must be replaced by local business definitions."]

    key = _make_key(object_name)
    source_type = "duckdb_view" if obj.get("object_kind") == "view" else "duckdb_table"
    entry = {
        "source_id": key,
        "key": key,
        "type": source_type,
        "source_backend": "duckdb",
        "display_name": display_name,
        "description": description,
        "status": "active",
        "category": category,
        "tags": ["duckdb", category],
        "duckdb": {
            "db_path": obj.get("db_path", DB_RELATIVE_PATH),
            "schema": obj.get("schema", "main"),
            "object_name": object_name,
            "object_kind": obj.get("object_kind"),
        },
        "fields": fields,
        "semantics": {
            "grain": grain,
            "primary_dimensions": dimensions,
            "available_metrics": measures,
            "time_fields": time_fields,
            "suitable_for": suitable_for,
            "not_suitable_for": not_suitable_for,
        },
        "agent": {
            "default_template": "executive_onepage",
            "suggested_questions": suitable_for[:3],
        },
    }

    spec = {
        "entry_key": key,
        "display_name": display_name,
        "updated": obj.get("updated", "2026-04-28"),
        "db_path": obj.get("db_path", DB_RELATIVE_PATH),
        "schema": obj.get("schema", "main"),
        "object_name": object_name,
        "object_kind": obj.get("object_kind"),
        "recommended_usage": obj.get("recommended_usage"),
        "business_domain": category,
        "row_count": obj.get("row_count"),
        "grain": grain,
        "time_fields": time_fields,
        "dimensions": [{"name": x, "data_type": "string"} for x in dimensions],
        "measures": [{"name": x, "data_type": "number"} for x in measures],
        "filters": [{"key": x, "display_name": x, "apply_via": "sql_where"} for x in dimensions[:20]],
        "fields": fields,
        "recommended_questions": suitable_for,
        "limitations": limitations,
        "category_display_name": category,
    }
    return entry, spec


def register(catalog_path: Path, *, dry_run: bool = False) -> list[str]:
    catalog = _load_catalog(catalog_path)
    saved: list[str] = []
    for obj in catalog.get("objects", []):
        built = _build_entry(obj)
        if not built:
            continue
        entry, spec = built
        if not dry_run:
            save_entry(entry)
            save_spec(spec)
        saved.append(entry["source_id"])
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Register example DuckDB sync snapshots into the unified SQLite registry")
    parser.add_argument("--catalog", default=str(CATALOG_PATH), help="DuckDB catalog JSON path")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    saved = register(Path(args.catalog), dry_run=args.dry_run)
    print(json.dumps({"count": len(saved), "sources": saved}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
