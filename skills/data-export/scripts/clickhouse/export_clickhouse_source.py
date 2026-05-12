#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
if str(SQL_DIR) not in sys.path:
    sys.path.insert(0, str(SQL_DIR))

import common_sql_export as common  # noqa: E402


WORKSPACE_DIR = common.find_workspace_root(Path(__file__).resolve())
common.add_workspace_path(WORKSPACE_DIR)


class ClickHouseClient:
    def __init__(self, meta: dict[str, Any]) -> None:
        try:
            import clickhouse_connect  # type: ignore[import-not-found]
        except ImportError as exc:
            raise SystemExit("clickhouse-connect is required. Install dependencies with: pip install -r requirements.txt") from exc
        config = common.load_connection_json(meta)
        self._client = clickhouse_connect.get_client(**config)

    def query(self, sql: str, params: list[Any]) -> tuple[list[str], list[tuple[Any, ...]]]:
        bound_sql = sql
        bound_params: dict[str, Any] = {}
        for index, value in enumerate(params):
            name = f"p{index}"
            bound_sql = bound_sql.replace("%s", f"{{{name}:String}}", 1)
            bound_params[name] = value
        result = self._client.query(bound_sql, parameters=bound_params)
        return list(result.column_names), [tuple(row) for row in result.result_rows]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Controlled export from a registry-managed ClickHouse source")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output-name", required=True)
    parser.add_argument("--select")
    parser.add_argument("--filter", action="append", default=[], help="field=value | field!=value | field~keyword")
    parser.add_argument("--date-range", action="append", default=[], help="field:start:end")
    parser.add_argument("--group-by")
    parser.add_argument("--aggregate", action="append", default=[], help="field:function:alias")
    parser.add_argument("--order-by", action="append", default=[], help="field:asc|desc")
    parser.add_argument("--limit", type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    entry, _spec, meta = common.ensure_valid_source(args.source_id, "clickhouse")
    del entry
    payload = common.run_export(
        workspace=WORKSPACE_DIR,
        connector="clickhouse",
        source_id=args.source_id,
        session_id=args.session_id,
        output_name=args.output_name,
        selected_fields=common.parse_csv_list(args.select),
        filters=[common.parse_filter(item) for item in args.filter],
        date_ranges=[common.parse_date_range(item) for item in args.date_range],
        group_by=common.parse_csv_list(args.group_by),
        aggregates=[common.parse_aggregate(item) for item in args.aggregate],
        order_by=[common.parse_order(item) for item in args.order_by],
        limit=args.limit,
        client=ClickHouseClient(meta),
        placeholder="%s",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
