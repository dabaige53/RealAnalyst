#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

def _find_workspace_root(start: Path) -> Path:
    env_root = os.environ.get("ANALYST_WORKSPACE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()

    for candidate in [start.parent, *start.parents]:
        if (candidate / "runtime").is_dir() and (
            (candidate / ".agents" / "skills").is_dir() or (candidate / "skills").is_dir()
        ):
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE_DIR = _find_workspace_root(Path(__file__).resolve())
SITE_PACKAGES = next(
    ((WORKSPACE_DIR / ".venv" / "lib").glob("python*/site-packages")),
    None,
)
if SITE_PACKAGES and str(SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(SITE_PACKAGES))
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.append(str(WORKSPACE_DIR))

try:
    import duckdb  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - dependency check
    duckdb = None  # type: ignore[assignment]
from runtime.tableau.sqlite_store import get_entry_by_source_id, load_spec_by_entry_key  # noqa: E402

ALLOWED_AGGS = {"sum", "avg", "min", "max", "count"}
ORDER_RE = re.compile(r"^(?P<field>.+?):(?P<direction>asc|desc)$", re.IGNORECASE)
DATE_RANGE_RE = re.compile(r"^(?P<field>.+?):(?P<start>.+?):(?P<end>.+?)$")
FILTER_OPERATORS = ["!=", "=", "~"]


def _parse_csv_list(text: str | None) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _parse_filter(expr: str) -> dict[str, str]:
    for op in FILTER_OPERATORS:
        if op in expr:
            field, value = expr.split(op, 1)
            return {"field": field.strip(), "operator": op, "value": value.strip()}
    raise ValueError(f"非法 filter 语法: {expr}")


def _parse_date_range(expr: str) -> dict[str, str]:
    m = DATE_RANGE_RE.match(expr)
    if not m:
        raise ValueError(f"非法 date-range 语法: {expr}")
    return m.groupdict()


def _parse_order(expr: str) -> dict[str, str]:
    m = ORDER_RE.match(expr)
    if not m:
        raise ValueError(f"非法 order-by 语法: {expr}")
    out = m.groupdict()
    out["direction"] = out["direction"].lower()
    return out


def _parse_aggregate(expr: str) -> dict[str, str]:
    parts = [x.strip() for x in expr.split(":")]
    if len(parts) != 3:
        raise ValueError(f"非法 aggregate 语法: {expr}")
    field, func, alias = parts
    func = func.lower()
    if func not in ALLOWED_AGGS:
        raise ValueError(f"不支持的聚合函数: {func}")
    if not alias:
        raise ValueError("aggregate alias 不能为空")
    return {"field": field, "function": func, "alias": alias}


def _allowed_fields(entry: dict[str, Any], spec: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for name in entry.get("fields", []) or []:
        if isinstance(name, str) and name.strip():
            out.add(name.strip())
    for key in ["fields", "time_fields", "grain", "recommended_questions"]:
        for item in spec.get(key, []) or []:
            if isinstance(item, str) and item.strip():
                out.add(item.strip())
    for section in ["dimensions", "measures", "filters"]:
        for item in spec.get(section, []) or []:
            if isinstance(item, dict):
                for k in ["name", "key", "display_name"]:
                    value = item.get(k)
                    if isinstance(value, str) and value.strip():
                        out.add(value.strip())
    return out


def _build_sql(
    object_name: str,
    selected_fields: list[str],
    filters: list[dict[str, str]],
    date_ranges: list[dict[str, str]],
    group_by: list[str],
    aggregates: list[dict[str, str]],
    order_by: list[dict[str, str]],
    limit: int | None,
) -> str:
    select_parts: list[str] = []
    if aggregates:
        for field in group_by:
            select_parts.append(_quote_ident(field))
        for agg in aggregates:
            select_parts.append(
                f"{agg['function'].upper()}({_quote_ident(agg['field'])}) AS {_quote_ident(agg['alias'])}"
            )
    else:
        cols = selected_fields or group_by
        if not cols:
            raise ValueError("未提供 select/group-by/aggregate，无法构造 SQL")
        select_parts.extend(_quote_ident(c) for c in cols)

    where_parts: list[str] = []
    for flt in filters:
        col = _quote_ident(flt["field"])
        if flt["operator"] == "=":
            where_parts.append(f"{col} = ?")
        elif flt["operator"] == "!=":
            where_parts.append(f"{col} != ?")
        elif flt["operator"] == "~":
            where_parts.append(f"CAST({col} AS VARCHAR) LIKE ?")
        else:
            raise ValueError(f"不支持 operator: {flt['operator']}")
    for dr in date_ranges:
        col = _quote_ident(dr["field"])
        where_parts.append(f"CAST({col} AS DATE) BETWEEN ? AND ?")

    sql = f"SELECT {', '.join(select_parts)} FROM {_quote_ident(object_name)}"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    if aggregates and group_by:
        sql += " GROUP BY " + ", ".join(_quote_ident(c) for c in group_by)
    if order_by:
        sql += " ORDER BY " + ", ".join(
            f"{_quote_ident(item['field'])} {item['direction'].upper()}" for item in order_by
        )
    if limit is not None:
        sql += f" LIMIT {limit}"
    return sql


def _build_params(filters: list[dict[str, str]], date_ranges: list[dict[str, str]]) -> list[str]:
    params: list[str] = []
    for flt in filters:
        if flt["operator"] == "~":
            params.append(f"%{flt['value']}%")
        else:
            params.append(flt["value"])
    for dr in date_ranges:
        params.extend([dr["start"], dr["end"]])
    return params


def _ensure_valid_source(source_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    entry = get_entry_by_source_id(source_id)
    if not entry:
        raise ValueError(f"未找到 source_id: {source_id}")
    if entry.get("source_backend") != "duckdb":
        raise ValueError(f"source_id 不是 duckdb 后端: {source_id}")
    if entry.get("status") != "active":
        raise ValueError(f"source_id 未激活: {source_id}")
    duckdb_meta = entry.get("duckdb") or {}
    object_name = str(duckdb_meta.get("object_name") or "")
    if object_name.startswith("TEMP_") or object_name.startswith("ToDrop_"):
        raise ValueError(f"禁止导出临时/废弃对象: {object_name}")
    spec = load_spec_by_entry_key(str(entry.get("key"))) or {}
    if not spec:
        raise ValueError(f"source 缺少 spec: {source_id}")
    return entry, spec


def _validate_fields(used_fields: list[str], allowed: set[str]) -> None:
    invalid = [f for f in used_fields if f not in allowed]
    if invalid:
        raise ValueError(f"存在未注册字段: {invalid}")


def _write_csv(rows: list[tuple[Any, ...]], headers: list[str], output_file: Path) -> int:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlled export from a registry-managed DuckDB source")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output-name", required=True)
    parser.add_argument("--select", help="Comma-separated registered fields")
    parser.add_argument("--filter", action="append", default=[], help="field=value | field!=value | field~keyword")
    parser.add_argument("--date-range", action="append", default=[], help="field:start:end")
    parser.add_argument("--group-by", help="Comma-separated fields")
    parser.add_argument("--aggregate", action="append", default=[], help="field:function:alias")
    parser.add_argument("--order-by", action="append", default=[], help="field:asc|desc")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    entry, spec = _ensure_valid_source(args.source_id)
    allowed = _allowed_fields(entry, spec)

    selected_fields = _parse_csv_list(args.select)
    group_by = _parse_csv_list(args.group_by)
    filters = [_parse_filter(x) for x in args.filter]
    date_ranges = [_parse_date_range(x) for x in args.date_range]
    aggregates = [_parse_aggregate(x) for x in args.aggregate]
    order_by = [_parse_order(x) for x in args.order_by]

    used_fields = []
    used_fields.extend(selected_fields)
    used_fields.extend(group_by)
    used_fields.extend([x["field"] for x in filters])
    used_fields.extend([x["field"] for x in date_ranges])
    used_fields.extend([x["field"] for x in aggregates])
    used_fields.extend([x["field"] for x in order_by])
    _validate_fields(used_fields, allowed)

    if aggregates and not group_by and not selected_fields:
        pass
    elif aggregates and selected_fields:
        raise ValueError("使用 aggregate 时不要再传 --select；请改用 --group-by + --aggregate")

    duckdb_meta = entry["duckdb"]
    db_path = WORKSPACE_DIR / str(duckdb_meta["db_path"])
    object_name = str(duckdb_meta["object_name"])

    sql = _build_sql(
        object_name=object_name,
        selected_fields=selected_fields,
        filters=filters,
        date_ranges=date_ranges,
        group_by=group_by,
        aggregates=aggregates,
        order_by=order_by,
        limit=args.limit,
    )
    params = _build_params(filters, date_ranges)

    if duckdb is None:
        raise SystemExit("duckdb is required. Install dependencies with: pip install -r requirements.txt")

    con = duckdb.connect(str(db_path), read_only=True)
    cur = con.execute(sql, params)
    rows = cur.fetchall()
    headers = [d[0] for d in cur.description]

    jobs_dir = WORKSPACE_DIR / "jobs" / args.session_id
    output_dir = jobs_dir
    output_file = output_dir / "data" / args.output_name
    row_count = _write_csv(rows, headers, output_file)

    summary = {
        "source_backend": "duckdb",
        "source_id": args.source_id,
        "display_name": entry.get("display_name"),
        "db_path": str(duckdb_meta["db_path"]),
        "schema": duckdb_meta.get("schema", "main"),
        "object_name": object_name,
        "output_file": str(output_file.relative_to(WORKSPACE_DIR)),
        "row_count": row_count,
        "selected_fields": headers,
        "filters": filters,
        "date_ranges": date_ranges,
        "group_by": group_by,
        "aggregates": aggregates,
        "order_by": order_by,
        "limit": args.limit,
        "sql": sql,
        "exported_at": datetime.now().astimezone().isoformat(),
    }
    summary_path = output_dir / "duckdb_export_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"output_file": str(output_file), "summary_file": str(summary_path), "row_count": row_count}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
