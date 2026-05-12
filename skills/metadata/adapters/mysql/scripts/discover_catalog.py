#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def _connection_payload(ref: str) -> dict[str, Any]:
    raw = os.environ.get(ref)
    if not raw:
        raise SystemExit(f"connection environment variable is not set: {ref}")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise SystemExit(f"connection env must contain JSON object: {ref}")
    return payload


def _snapshot(args: argparse.Namespace, columns: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "connector": "mysql",
        "source_id": args.source_id,
        "database": args.database,
        "schema": args.schema or args.database,
        "table": args.table,
        "object_kind": args.object_kind,
        "connection_ref": args.connection_ref,
        "credential_ref": args.credential_ref,
        "dsn_env": args.dsn_env,
        "columns": columns,
        "generated_at": datetime.now().astimezone().isoformat(),
        "boundary": "Catalog snapshot only; archive as evidence/material, not business definition truth.",
    }


def _discover(args: argparse.Namespace) -> list[dict[str, Any]]:
    try:
        import pymysql  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit("pymysql is required. Install dependencies with: pip install -r requirements.txt") from exc
    ref = args.connection_ref or args.credential_ref or args.dsn_env
    if not ref:
        raise SystemExit("--connection-ref, --credential-ref, or --dsn-env is required without --dry-run")
    config = _connection_payload(ref)
    conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **config)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
                """,
                [args.schema or args.database, args.table],
            )
            rows = cursor.fetchall()
    finally:
        conn.close()
    return [
        {
            "name": row.get("COLUMN_NAME"),
            "type": row.get("DATA_TYPE"),
            "nullable": row.get("IS_NULLABLE") == "YES",
            "key": row.get("COLUMN_KEY"),
        }
        for row in rows
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover a MySQL table catalog snapshot for metadata registration")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--schema", default="")
    parser.add_argument("--table", required=True)
    parser.add_argument("--object-kind", choices=("table", "view"), default="table")
    parser.add_argument("--connection-ref", default="", help="Environment variable containing JSON connection config")
    parser.add_argument("--credential-ref", default="", help="Environment variable containing JSON connection config")
    parser.add_argument("--dsn-env", default="", help="Environment variable containing JSON connection config")
    parser.add_argument("--output", default="", help="Optional output JSON path under metadata/sync/mysql/")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    columns: list[dict[str, Any]] = [] if args.dry_run else _discover(args)
    payload = _snapshot(args, columns)
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
