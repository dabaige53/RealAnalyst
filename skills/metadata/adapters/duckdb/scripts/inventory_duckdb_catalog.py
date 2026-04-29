#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _object_role(name: str, table_type: str) -> str:
    upper = name.upper()
    if upper.startswith("DIM_"):
        return "dimension"
    if upper.startswith("APP_"):
        return "app"
    if upper.startswith("ODS_"):
        return "fact"
    if upper.startswith("TEMP_"):
        return "temp"
    if upper.startswith("TODROP_"):
        return "deprecated"
    if table_type.upper() == "VIEW" or upper.startswith("VIEW_"):
        return "view"
    return "unknown"


def _business_domain(name: str) -> str:
    upper = name.upper()
    if "OAG" in upper:
        return "market_capacity"
    if "DIH" in upper:
        return "flight_change_log"
    if "BUDGET" in upper:
        return "budget_plan"
    if "RESULT" in upper:
        return "flight_result"
    if "AIRPORT" in upper:
        return "airport"
    if "AIRLINE" in upper:
        return "airline"
    if "SALES_OFFICE" in upper:
        return "sales_office"
    if "TRAVEL_AGENC" in upper:
        return "travel_agency"
    if "DATE" in upper:
        return "date_dimension"
    if "MATCH" in upper or "BENCHMARK" in upper:
        return "benchmark_matching"
    if "PROFILE" in upper:
        return "flight_profile"
    if "FLIGHT" in upper:
        return "flight_operation"
    return "other"


def _recommended_usage(role: str, name: str, row_count: int) -> str:
    upper = name.upper()
    if role in {"temp", "deprecated"}:
        return "exclude_by_default"
    if role == "dimension":
        return "dimension_lookup_only"
    if role == "view":
        return "analysis_ready"
    if upper.startswith("ODS_") and row_count > 0:
        return "analysis_ready"
    if upper.startswith("APP_"):
        return "analysis_ready_with_context"
    return "review_manually"


def _sample_values(con: duckdb.DuckDBPyConnection, relation: str, column: str, limit: int = 5) -> list[str]:
    try:
        rows = con.execute(
            f'SELECT DISTINCT "{column}" FROM "{relation}" WHERE "{column}" IS NOT NULL LIMIT {limit}'
        ).fetchall()
        return [str(r[0]) for r in rows if r and r[0] is not None]
    except Exception:
        return []


def inventory_database(db_path: Path) -> dict[str, Any]:
    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    tables = con.execute(
        """
        SELECT table_schema, table_name, table_type
        FROM information_schema.tables
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY table_schema, table_name
        """
    ).fetchall()

    objects: list[dict[str, Any]] = []
    for schema, table_name, table_type in tables:
        describe_rows = con.execute(f'DESCRIBE SELECT * FROM "{table_name}"').fetchall()
        columns: list[dict[str, str]] = [
            {"name": row[0], "type": row[1]} for row in describe_rows
        ]
        row_count = con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        time_fields = [c["name"] for c in columns if any(x in c["type"].upper() for x in ["DATE", "TIME"])]
        numeric_fields = [
            c["name"] for c in columns if any(x in c["type"].upper() for x in ["INT", "DOUBLE", "REAL", "DECIMAL", "FLOAT"])
        ]
        role = _object_role(table_name, table_type)
        domain = _business_domain(table_name)
        usage = _recommended_usage(role, table_name, row_count)
        sample_columns = []
        for c in columns[: min(3, len(columns))]:
            sample_columns.append(
                {
                    "name": c["name"],
                    "samples": _sample_values(con, table_name, c["name"]),
                }
            )
        objects.append(
            {
                "schema": schema,
                "object_name": table_name,
                "object_kind": table_type.lower(),
                "object_role": role,
                "business_domain": domain,
                "recommended_usage": usage,
                "row_count": row_count,
                "column_count": len(columns),
                "time_fields": time_fields,
                "numeric_fields": numeric_fields[:20],
                "columns": columns,
                "sample_columns": sample_columns,
            }
        )

    return {
        "db_path": str(db_path),
        "object_count": len(objects),
        "objects": objects,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory a DuckDB database into JSON catalog")
    parser.add_argument("db_path", help="Path to DuckDB database")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    catalog = inventory_database(db_path)
    output_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
