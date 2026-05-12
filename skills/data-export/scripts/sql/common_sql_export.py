#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


class QueryClient(Protocol):
    def query(self, sql: str, params: list[Any]) -> tuple[list[str], list[tuple[Any, ...]]]:
        ...


ALLOWED_AGGS = {"sum", "avg", "min", "max", "count"}
ORDER_RE = re.compile(r"^(?P<field>.+?):(?P<direction>asc|desc)$", re.IGNORECASE)
DATE_RANGE_RE = re.compile(r"^(?P<field>.+?):(?P<start>.+?):(?P<end>.+?)$")
FILTER_OPERATORS = ["!=", "=", "~"]
SAFE_OUTPUT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def find_workspace_root(start: Path) -> Path:
    env_root = os.environ.get("ANALYST_WORKSPACE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()
    for candidate in [start.parent, *start.parents]:
        if (candidate / "runtime").is_dir() and ((candidate / ".agents" / "skills").is_dir() or (candidate / "skills").is_dir()):
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


def add_workspace_path(workspace: Path) -> None:
    if str(workspace) not in sys.path:
        sys.path.append(str(workspace))


def parse_csv_list(text: str | None) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def parse_filter(expr: str) -> dict[str, str]:
    for op in FILTER_OPERATORS:
        if op in expr:
            field, value = expr.split(op, 1)
            return {"field": field.strip(), "operator": op, "value": value.strip()}
    raise ValueError(f"非法 filter 语法: {expr}")


def parse_date_range(expr: str) -> dict[str, str]:
    match = DATE_RANGE_RE.match(expr)
    if not match:
        raise ValueError(f"非法 date-range 语法: {expr}")
    return match.groupdict()


def parse_order(expr: str) -> dict[str, str]:
    match = ORDER_RE.match(expr)
    if not match:
        raise ValueError(f"非法 order-by 语法: {expr}")
    out = match.groupdict()
    out["direction"] = out["direction"].lower()
    return out


def parse_aggregate(expr: str) -> dict[str, str]:
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


def quote_ident(name: str, connector: str) -> str:
    quote = "`" if connector in {"mysql", "clickhouse"} else '"'
    return quote + name.replace(quote, quote + quote) + quote


def safe_ref(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if "://" in text or "@" in text or "password" in lowered or "token" in lowered or "\n" in text:
        return "[redacted]"
    return text


def resolve_output_file(workspace: Path, session_id: str, output_name: str) -> Path:
    clean_name = output_name.strip()
    if not clean_name or not SAFE_OUTPUT_RE.match(clean_name):
        raise ValueError("--output-name must be a simple file name using letters, numbers, dot, dash, or underscore")
    output_dir = (workspace / "jobs" / session_id / "data").resolve()
    output_file = (output_dir / clean_name).resolve()
    try:
        output_file.relative_to(output_dir)
    except ValueError as exc:
        raise ValueError("--output-name escapes the job data directory") from exc
    return output_file


def allowed_fields(entry: dict[str, Any], spec: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for name in entry.get("fields", []) or []:
        if isinstance(name, str) and name.strip():
            out.add(name.strip())
    for key in ["fields", "time_fields", "grain"]:
        for item in spec.get(key, []) or []:
            if isinstance(item, str) and item.strip():
                out.add(item.strip())
    for section in ["dimensions", "measures", "filters"]:
        for item in spec.get(section, []) or []:
            if isinstance(item, dict):
                for key in ["name", "key", "display_name"]:
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        out.add(value.strip())
    return out


def validate_fields(used_fields: list[str], allowed: set[str]) -> None:
    invalid = [field for field in used_fields if field not in allowed]
    if invalid:
        raise ValueError(f"存在未注册字段: {invalid}")


def relation_name(meta: dict[str, Any], connector: str) -> str:
    object_name = str(meta.get("object_name") or meta.get("table") or "").strip()
    if not object_name:
        raise ValueError(f"{connector} source missing object_name/table")
    if object_name.startswith("TEMP_") or object_name.startswith("ToDrop_"):
        raise ValueError(f"禁止导出临时/废弃对象: {object_name}")
    namespace = str(meta.get("schema") or meta.get("database") or "").strip()
    if namespace:
        return f"{quote_ident(namespace, connector)}.{quote_ident(object_name, connector)}"
    return quote_ident(object_name, connector)


def build_sql(
    *,
    connector: str,
    relation: str,
    placeholder: str,
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
            select_parts.append(quote_ident(field, connector))
        for agg in aggregates:
            select_parts.append(f"{agg['function'].upper()}({quote_ident(agg['field'], connector)}) AS {quote_ident(agg['alias'], connector)}")
    else:
        cols = selected_fields or group_by
        if not cols:
            raise ValueError("未提供 select/group-by/aggregate，无法构造 SQL")
        select_parts.extend(quote_ident(col, connector) for col in cols)

    where_parts: list[str] = []
    for flt in filters:
        col = quote_ident(flt["field"], connector)
        if flt["operator"] == "=":
            where_parts.append(f"{col} = {placeholder}")
        elif flt["operator"] == "!=":
            where_parts.append(f"{col} != {placeholder}")
        elif flt["operator"] == "~":
            where_parts.append(f"CAST({col} AS CHAR) LIKE {placeholder}" if connector == "mysql" else f"toString({col}) LIKE {placeholder}")
        else:
            raise ValueError(f"不支持 operator: {flt['operator']}")
    for dr in date_ranges:
        col = quote_ident(dr["field"], connector)
        where_parts.append(f"CAST({col} AS DATE) BETWEEN {placeholder} AND {placeholder}")

    sql = f"SELECT {', '.join(select_parts)} FROM {relation}"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    if aggregates and group_by:
        sql += " GROUP BY " + ", ".join(quote_ident(col, connector) for col in group_by)
    if order_by:
        sql += " ORDER BY " + ", ".join(f"{quote_ident(item['field'], connector)} {item['direction'].upper()}" for item in order_by)
    if limit is not None:
        if limit < 0:
            raise ValueError("--limit must be zero or greater")
        sql += f" LIMIT {int(limit)}"
    return sql


def build_params(filters: list[dict[str, str]], date_ranges: list[dict[str, str]]) -> list[str]:
    params: list[str] = []
    for flt in filters:
        params.append(f"%{flt['value']}%" if flt["operator"] == "~" else flt["value"])
    for dr in date_ranges:
        params.extend([dr["start"], dr["end"]])
    return params


def connection_ref(meta: dict[str, Any]) -> str:
    for key in ("connection_ref", "credential_ref", "dsn_env"):
        value = str(meta.get(key) or "").strip()
        if value:
            return value
    raise ValueError("source missing connection_ref, credential_ref, or dsn_env")


def load_connection_json(meta: dict[str, Any]) -> dict[str, Any]:
    ref = connection_ref(meta)
    raw = os.environ.get(ref)
    if not raw:
        raise ValueError(f"connection environment variable is not set: {ref}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"connection env must contain JSON object: {ref}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"connection env must contain JSON object: {ref}")
    return payload


def ensure_valid_source(source_id: str, connector: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    from runtime.tableau.sqlite_store import get_entry_by_source_id, load_spec_by_entry_key

    entry = get_entry_by_source_id(source_id)
    if not entry:
        raise ValueError(f"未找到 source_id: {source_id}")
    if entry.get("source_backend") != connector:
        raise ValueError(f"source_id 不是 {connector} 后端: {source_id}")
    if entry.get("status") != "active":
        raise ValueError(f"source_id 未激活: {source_id}")
    spec = load_spec_by_entry_key(str(entry.get("key"))) or {}
    if not spec:
        raise ValueError(f"source 缺少 spec: {source_id}")
    meta = entry.get(connector) if isinstance(entry.get(connector), dict) else {}
    relation_name(meta, connector)
    connection_ref(meta)
    return entry, spec, meta


def write_csv(rows: list[tuple[Any, ...]], headers: list[str], output_file: Path) -> int:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    return len(rows)


def run_export(
    *,
    workspace: Path,
    connector: str,
    source_id: str,
    session_id: str,
    output_name: str,
    selected_fields: list[str],
    filters: list[dict[str, str]],
    date_ranges: list[dict[str, str]],
    group_by: list[str],
    aggregates: list[dict[str, str]],
    order_by: list[dict[str, str]],
    limit: int | None,
    client: QueryClient,
    placeholder: str,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    entry, spec, meta = ensure_valid_source(source_id, connector)
    allowed = allowed_fields(entry, spec)
    used_fields: list[str] = []
    used_fields.extend(selected_fields)
    used_fields.extend(group_by)
    used_fields.extend([item["field"] for item in filters])
    used_fields.extend([item["field"] for item in date_ranges])
    used_fields.extend([item["field"] for item in aggregates])
    aggregate_aliases = {item["alias"] for item in aggregates}
    used_fields.extend([item["field"] for item in order_by if item["field"] not in aggregate_aliases])
    validate_fields(used_fields, allowed)
    if aggregates and selected_fields:
        raise ValueError("使用 aggregate 时不要再传 --select；请改用 --group-by + --aggregate")

    relation = relation_name(meta, connector)
    sql = build_sql(
        connector=connector,
        relation=relation,
        placeholder=placeholder,
        selected_fields=selected_fields,
        filters=filters,
        date_ranges=date_ranges,
        group_by=group_by,
        aggregates=aggregates,
        order_by=order_by,
        limit=limit,
    )
    params = build_params(filters, date_ranges)
    headers, rows = client.query(sql, params)

    job_dir = workspace / "jobs" / session_id
    output_file = resolve_output_file(workspace, session_id, output_name)
    row_count = write_csv(rows, headers, output_file)
    exported_at = datetime.now().astimezone().isoformat()
    summary = {
        "source_backend": connector,
        "source_id": source_id,
        "display_name": entry.get("display_name"),
        "database": meta.get("database"),
        "schema": meta.get("schema"),
        "object_name": meta.get("object_name") or meta.get("table"),
        "object_kind": meta.get("object_kind"),
        "connection_ref": safe_ref(meta.get("connection_ref")),
        "credential_ref": safe_ref(meta.get("credential_ref")),
        "dsn_env": safe_ref(meta.get("dsn_env")),
        "output_file": str(output_file.relative_to(workspace)),
        "row_count": row_count,
        "selected_fields": headers,
        "filters": filters,
        "date_ranges": date_ranges,
        "group_by": group_by,
        "aggregates": aggregates,
        "order_by": order_by,
        "limit": limit,
        "sql": sql,
        "exported_at": exported_at,
    }
    summary_path = job_dir / f"{connector}_export_summary_{Path(output_name).stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    latest_path = job_dir / f"{connector}_export_summary.json"
    neutral_path = job_dir / "data_export_summary.json"
    for path in (summary_path, latest_path, neutral_path):
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "output_file": str(output_file),
        "summary_file": str(summary_path),
        "latest_summary_file": str(latest_path),
        "neutral_summary_file": str(neutral_path),
        "row_count": row_count,
    }
