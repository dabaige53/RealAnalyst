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


class MySQLClient:
    def __init__(self, meta: dict[str, Any]) -> None:
        try:
            import pymysql  # type: ignore[import-not-found]
        except ImportError as exc:
            raise SystemExit("pymysql is required. Install dependencies with: pip install -r requirements.txt") from exc
        config = common.load_connection_json(meta)
        self._conn = pymysql.connect(cursorclass=pymysql.cursors.Cursor, **config)

    def query(self, sql: str, params: list[Any]) -> tuple[list[str], list[tuple[Any, ...]]]:
        with self._conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            headers = [desc[0] for desc in cursor.description or []]
        self._conn.close()
        return headers, [tuple(row) for row in rows]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Controlled export from a registry-managed MySQL source")
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
    entry, _spec, meta = common.ensure_valid_source(args.source_id, "mysql")
    del entry
    payload = common.run_export(
        workspace=WORKSPACE_DIR,
        connector="mysql",
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
        client=MySQLClient(meta),
        placeholder="%s",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
