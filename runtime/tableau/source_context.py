#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sqlite3
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

WORKSPACE_DIR = Path(__file__).resolve().parents[2]
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

try:
    from sqlite_store import load_spec_by_entry_key, load_spec_by_ref, load_spec_for_entry
except ModuleNotFoundError:  # pragma: no cover - package import path
    from runtime.tableau.sqlite_store import load_spec_by_entry_key, load_spec_by_ref, load_spec_for_entry

from runtime.runtime_config_store import db_path as runtime_db_path, ensure_store_ready as ensure_runtime_ready  # noqa: E402

RUNTIME_DB = runtime_db_path()
MAPPINGS_PATH = Path(__file__).resolve().parent / "source_context_mappings.yaml"

_STATUS_MAPPED = "mapped"
_STATUS_UNRESOLVED = "unresolved"
_STATUS_ROLE_MISMATCH = "role_mismatch"
_STATUS_OVERRIDE_ERROR = "override_error"


def _norm_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).lower()


@lru_cache(maxsize=1)
def _load_mappings() -> dict[str, Any]:
    if not MAPPINGS_PATH.exists():
        return {}
    data = yaml.safe_load(MAPPINGS_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def _load_metric_index() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    ensure_runtime_ready()
    conn = sqlite3.connect(RUNTIME_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    rows = cur.execute(
        """
        select metric_id, name_cn, aliases_json, unit, definition, category_name, benchmark_json, payload_json
        from metrics
        order by metric_id
        """
    ).fetchall()

    for row in rows:
        aliases: list[str] = []
        try:
            loaded_aliases = json.loads(row["aliases_json"] or "[]")
            if isinstance(loaded_aliases, list):
                aliases = [str(x).strip() for x in loaded_aliases if str(x).strip()]
        except json.JSONDecodeError:
            aliases = []

        benchmark: dict[str, Any] = {}
        try:
            loaded_benchmark = json.loads(row["benchmark_json"] or "{}")
            if isinstance(loaded_benchmark, dict):
                benchmark = loaded_benchmark
        except json.JSONDecodeError:
            benchmark = {}

        payload: dict[str, Any] = {}
        try:
            loaded_payload = json.loads(row["payload_json"] or "{}")
            if isinstance(loaded_payload, dict):
                payload = loaded_payload
        except json.JSONDecodeError:
            payload = {}

        record = {
            "metric_id": row["metric_id"],
            "name_cn": row["name_cn"],
            "aliases": aliases,
            "unit": row["unit"],
            "definition": row["definition"],
            "category_name": row["category_name"],
            "benchmark": benchmark,
            "payload": payload,
        }
        metric_id = str(row["metric_id"])
        by_id[metric_id] = record

        names = [str(row["name_cn"] or "").strip(), *aliases]
        for name in names:
            if not name:
                continue
            by_name.setdefault(_norm_text(name), []).append(record)

    return by_id, by_name


@lru_cache(maxsize=1)
def _load_dimension_index() -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    ensure_runtime_ready()
    conn = sqlite3.connect(RUNTIME_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    rows = cur.execute(
        """
        select d.dimension_id,
               d.name as dimension_name,
               d.category_name,
               f.field_id,
               f.field_name,
               f.field_type,
               f.definition,
               f.payload_json
        from dimension_fields f
        join dimensions d on d.dimension_id = f.dimension_id
        order by d.dimension_id, f.field_id
        """
    ).fetchall()

    for row in rows:
        payload: dict[str, Any] = {}
        try:
            loaded_payload = json.loads(row["payload_json"] or "{}")
            if isinstance(loaded_payload, dict):
                payload = loaded_payload
        except json.JSONDecodeError:
            payload = {}

        aliases = payload.get("aliases")
        alias_list = [str(x).strip() for x in aliases if str(x).strip()] if isinstance(aliases, list) else []
        record = {
            "dimension_id": row["dimension_id"],
            "dimension_name": row["dimension_name"],
            "category_name": row["category_name"],
            "field_id": row["field_id"],
            "field_name": row["field_name"],
            "field_type": row["field_type"],
            "definition": row["definition"],
            "aliases": alias_list,
            "payload": payload,
        }
        key = (str(row["dimension_id"]), str(row["field_id"]))
        by_key[key] = record

        names = [str(row["field_name"] or "").strip(), *alias_list]
        for name in names:
            if not name:
                continue
            by_name.setdefault(_norm_text(name), []).append(record)

    return by_key, by_name


def _get_fields_from_spec(spec: dict[str, Any]) -> list[str]:
    fields = spec.get("fields")
    if isinstance(fields, list) and all(isinstance(x, str) for x in fields):
        return [x for x in fields if x.strip()]

    derived: list[str] = []
    for section in ("dimensions", "measures"):
        items = spec.get(section)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name.strip():
                    derived.append(name.strip())
    seen: set[str] = set()
    out: list[str] = []
    for field in derived:
        if field in seen:
            continue
        seen.add(field)
        out.append(field)
    return out


def get_source_fields(src: dict[str, Any]) -> list[str]:
    spec = load_spec_for_entry(src)
    if isinstance(spec, dict):
        derived = _get_fields_from_spec(spec)
        if derived:
            return derived

    fields = src.get("fields")
    if isinstance(fields, list):
        out = [str(f).strip() for f in fields if str(f).strip()]
        if out:
            return out
    return []


def get_source_filters(src: dict[str, Any]) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    spec = load_spec_for_entry(src)
    if not isinstance(spec, dict):
        return filters

    raw_filters = spec.get("filters")
    if not isinstance(raw_filters, list):
        return filters

    for item in raw_filters:
        if not isinstance(item, dict):
            continue
        validation = item.get("validation") if isinstance(item.get("validation"), dict) else {}
        samples = item.get("sample_values") if isinstance(item.get("sample_values"), list) else []
        filters.append(
            {
                "key": item.get("key") or item.get("tableau_field"),
                "tableau_field": item.get("tableau_field"),
                "kind": item.get("kind") or "unknown",
                "description": item.get("description"),
                "sample_values": samples[:5],
                "validation": validation,
            }
        )
    return filters


def _dedupe_str_list(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        token = str(value or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _source_map(source_id: str, role: str) -> dict[str, Any]:
    mappings = _load_mappings()
    sources = mappings.get("sources")
    if not isinstance(sources, dict):
        return {}
    source_cfg = sources.get(source_id)
    if not isinstance(source_cfg, dict):
        return {}
    role_cfg = source_cfg.get(role)
    return role_cfg if isinstance(role_cfg, dict) else {}


def _metric_from_record(
    source_field: str,
    record: dict[str, Any],
    *,
    status: str,
    match_method: str,
    notes: str | None = None,
    name_override: str | None = None,
    definition_override: str | None = None,
    unit_override: str | None = None,
    subset_scope: str | None = None,
) -> dict[str, Any]:
    payload = {
        "source_field": source_field,
        "status": status,
        "match_method": match_method,
        "metric_id": record.get("metric_id"),
        "name_cn": name_override or record.get("name_cn"),
        "standard_name_cn": record.get("name_cn"),
        "unit": unit_override or record.get("unit"),
        "definition": definition_override or record.get("definition"),
        "standard_definition": record.get("definition"),
        "aliases": record.get("aliases", []),
        "category_name": record.get("category_name"),
        "benchmark": record.get("benchmark", {}),
    }
    if notes:
        payload["notes"] = notes
    if subset_scope:
        payload["subset_scope"] = subset_scope
    return {k: v for k, v in payload.items() if v not in (None, [], {}, "")}


def _dimension_from_record(
    source_field: str,
    record: dict[str, Any],
    *,
    status: str,
    match_method: str,
    notes: str | None = None,
    field_name_override: str | None = None,
    definition_override: str | None = None,
    field_type_override: str | None = None,
    enum_ref: str | None = None,
) -> dict[str, Any]:
    payload = {
        "source_field": source_field,
        "status": status,
        "match_method": match_method,
        "dimension_id": record.get("dimension_id"),
        "dimension_name": record.get("dimension_name"),
        "field_id": record.get("field_id"),
        "field_name": field_name_override or record.get("field_name"),
        "standard_field_name": record.get("field_name"),
        "field_type": field_type_override or record.get("field_type"),
        "definition": definition_override or record.get("definition"),
        "standard_definition": record.get("definition"),
        "aliases": record.get("aliases", []),
        "category_name": record.get("category_name"),
    }
    if notes:
        payload["notes"] = notes
    if enum_ref:
        payload["enum_ref"] = enum_ref
    return {k: v for k, v in payload.items() if v not in (None, [], {}, "")}


def _resolve_metric(source_id: str, field_name: str) -> dict[str, Any]:
    metric_by_id, metric_by_name = _load_metric_index()
    _, dimension_by_name = _load_dimension_index()
    overrides = _source_map(source_id, "metrics")
    override = overrides.get(field_name)
    if isinstance(override, dict):
        metric_id = override.get("metric_id")
        if isinstance(metric_id, str) and metric_id in metric_by_id:
            return _metric_from_record(
                field_name,
                metric_by_id[metric_id],
                status=_STATUS_MAPPED,
                match_method="override",
                notes=override.get("notes"),
                name_override=override.get("name_override"),
                definition_override=override.get("definition_override"),
                unit_override=override.get("unit_override"),
                subset_scope=override.get("subset_scope"),
            )
        return {
            "source_field": field_name,
            "status": _STATUS_OVERRIDE_ERROR,
            "match_method": "override",
            "error": f"未知 metric_id: {metric_id}",
        }

    matches = metric_by_name.get(_norm_text(field_name), [])
    if len(matches) == 1:
        match = matches[0]
        match_method = "exact_name" if _norm_text(str(match.get("name_cn") or "")) == _norm_text(field_name) else "exact_alias"
        return _metric_from_record(field_name, match, status=_STATUS_MAPPED, match_method=match_method)
    if len(matches) > 1:
        return {
            "source_field": field_name,
            "status": "ambiguous",
            "candidate_metric_ids": [m.get("metric_id") for m in matches],
        }

    dim_matches = dimension_by_name.get(_norm_text(field_name), [])
    if len(dim_matches) == 1:
        dim = dim_matches[0]
        return {
            "source_field": field_name,
            "status": _STATUS_ROLE_MISMATCH,
            "suggested_role": "dimension",
            "dimension_id": dim.get("dimension_id"),
            "field_id": dim.get("field_id"),
            "field_name": dim.get("field_name"),
            "dimension_name": dim.get("dimension_name"),
        }
    if len(dim_matches) > 1:
        return {
            "source_field": field_name,
            "status": _STATUS_ROLE_MISMATCH,
            "suggested_role": "dimension",
            "candidate_dimensions": [f"{m.get('dimension_id')}.{m.get('field_id')}" for m in dim_matches],
        }

    return {"source_field": field_name, "status": _STATUS_UNRESOLVED}


def _resolve_dimension(source_id: str, field_name: str) -> dict[str, Any]:
    dimension_by_key, dimension_by_name = _load_dimension_index()
    _, metric_by_name = _load_metric_index()
    overrides = _source_map(source_id, "dimensions")
    override = overrides.get(field_name)
    if isinstance(override, dict):
        dimension_id = override.get("dimension_id")
        field_id = override.get("field_id")
        lookup_key = (str(dimension_id), str(field_id))
        if lookup_key in dimension_by_key:
            return _dimension_from_record(
                field_name,
                dimension_by_key[lookup_key],
                status=_STATUS_MAPPED,
                match_method="override",
                notes=override.get("notes"),
                field_name_override=override.get("field_name_override"),
                definition_override=override.get("definition_override"),
                field_type_override=override.get("field_type_override"),
                enum_ref=override.get("enum_ref"),
            )
        return {
            "source_field": field_name,
            "status": _STATUS_OVERRIDE_ERROR,
            "match_method": "override",
            "error": f"未知 dimension 映射: {dimension_id}.{field_id}",
        }

    matches = dimension_by_name.get(_norm_text(field_name), [])
    if len(matches) == 1:
        match = matches[0]
        match_method = "exact_name" if _norm_text(str(match.get("field_name") or "")) == _norm_text(field_name) else "exact_alias"
        return _dimension_from_record(field_name, match, status=_STATUS_MAPPED, match_method=match_method)
    if len(matches) > 1:
        return {
            "source_field": field_name,
            "status": "ambiguous",
            "candidate_dimensions": [f"{m.get('dimension_id')}.{m.get('field_id')}" for m in matches],
        }

    metric_matches = metric_by_name.get(_norm_text(field_name), [])
    if len(metric_matches) == 1:
        metric = metric_matches[0]
        return {
            "source_field": field_name,
            "status": _STATUS_ROLE_MISMATCH,
            "suggested_role": "metric",
            "metric_id": metric.get("metric_id"),
            "name_cn": metric.get("name_cn"),
        }
    if len(metric_matches) > 1:
        return {
            "source_field": field_name,
            "status": _STATUS_ROLE_MISMATCH,
            "suggested_role": "metric",
            "candidate_metric_ids": [m.get("metric_id") for m in metric_matches],
        }

    return {"source_field": field_name, "status": _STATUS_UNRESOLVED}


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"total": len(items), "mapped": 0, "unresolved": 0, "role_mismatch": 0, "ambiguous": 0, "override_error": 0}
    for item in items:
        status = str(item.get("status") or "")
        if status in summary:
            summary[status] += 1
    return summary


def build_source_context(src: dict[str, Any]) -> dict[str, Any]:
    source_id = str(src.get("source_id") or "")
    semantics = src.get("semantics") if isinstance(src.get("semantics"), dict) else {}
    fields = get_source_fields(src)
    filters = get_source_filters(src)
    metric_candidates = _dedupe_str_list(semantics.get("available_metrics", []) if isinstance(semantics, dict) else [])
    dimension_candidates = _dedupe_str_list(semantics.get("primary_dimensions", []) if isinstance(semantics, dict) else [])

    metrics = [_resolve_metric(source_id, field_name) for field_name in metric_candidates]
    dimensions = [_resolve_dimension(source_id, field_name) for field_name in dimension_candidates]

    role_mismatches = [
        {"role": "metric", **item} for item in metrics if item.get("status") == _STATUS_ROLE_MISMATCH
    ] + [{"role": "dimension", **item} for item in dimensions if item.get("status") == _STATUS_ROLE_MISMATCH]

    context = {
        "version": "source-context.v1",
        "source_id": src.get("source_id"),
        "key": src.get("key"),
        "source_backend": src.get("source_backend") or ("duckdb" if str(src.get("type") or "").startswith("duckdb") else "tableau"),
        "type": src.get("type"),
        "display_name": src.get("display_name"),
        "description": src.get("description"),
        "category": src.get("category"),
        "grain": _dedupe_str_list(semantics.get("grain", []) if isinstance(semantics, dict) else []),
        "time_fields": _dedupe_str_list(semantics.get("time_fields", []) if isinstance(semantics, dict) else []),
        "suitable_for": _dedupe_str_list(semantics.get("suitable_for", []) if isinstance(semantics, dict) else []),
        "not_suitable_for": _dedupe_str_list(semantics.get("not_suitable_for", []) if isinstance(semantics, dict) else []),
        "suggested_questions": _dedupe_str_list((src.get("agent") or {}).get("suggested_questions", []) if isinstance(src.get("agent"), dict) else []),
        "source_fields": fields,
        "filters": filters,
        "metrics": metrics,
        "dimensions": dimensions,
        "unresolved_metrics": [item.get("source_field") for item in metrics if item.get("status") != _STATUS_MAPPED],
        "unresolved_dimensions": [item.get("source_field") for item in dimensions if item.get("status") != _STATUS_MAPPED],
        "role_mismatches": role_mismatches,
        "mapping_summary": {
            "metrics": _summary(metrics),
            "dimensions": _summary(dimensions),
        },
    }
    return context


def _status_cn(status: str) -> str:
    return {
        _STATUS_MAPPED: "已映射",
        _STATUS_UNRESOLVED: "未解析",
        _STATUS_ROLE_MISMATCH: "角色疑似不符",
        _STATUS_OVERRIDE_ERROR: "覆盖配置错误",
        "ambiguous": "存在歧义",
    }.get(status, status or "未知")


def _md_escape(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def render_context_markdown(context: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 数据源上下文包")
    lines.append("")
    lines.append(f"- 名称：{context.get('display_name', '')}")
    lines.append(f"- source_id：{context.get('source_id', '')}")
    lines.append(f"- 类型：{context.get('source_backend', '')} / {context.get('type', '')}")
    if context.get("description"):
        lines.append(f"- 描述：{context.get('description')}")
    if context.get("grain"):
        lines.append(f"- 粒度：{', '.join(context.get('grain', []))}")
    if context.get("time_fields"):
        lines.append(f"- 时间字段：{', '.join(context.get('time_fields', []))}")
    if context.get("suitable_for"):
        lines.append(f"- 适用场景：{', '.join(context.get('suitable_for', []))}")
    if context.get("not_suitable_for"):
        lines.append(f"- 不适用场景：{', '.join(context.get('not_suitable_for', []))}")
    lines.append("")

    lines.append("## 指标定义映射")
    lines.append("")
    lines.append("| 源字段 | 状态 | 标准指标ID | 标准指标名 | 单位 | 说明 |")
    lines.append("|---|---|---|---|---|---|")
    for item in context.get("metrics", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_escape(item.get("source_field", "")),
                    _md_escape(_status_cn(str(item.get("status", "")))),
                    _md_escape(item.get("metric_id", "")),
                    _md_escape(item.get("name_cn", "")),
                    _md_escape(item.get("unit", "")),
                    _md_escape(item.get("definition") or item.get("error") or item.get("suggested_role") or ""),
                ]
            )
            + " |"
        )
    lines.append("")

    lines.append("## 维度定义映射")
    lines.append("")
    lines.append("| 源字段 | 状态 | 维度ID | 字段ID | 标准字段名 | 类型 | 说明 |")
    lines.append("|---|---|---|---|---|---|---|")
    for item in context.get("dimensions", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_escape(item.get("source_field", "")),
                    _md_escape(_status_cn(str(item.get("status", "")))),
                    _md_escape(item.get("dimension_id", "")),
                    _md_escape(item.get("field_id", "")),
                    _md_escape(item.get("field_name", "")),
                    _md_escape(item.get("field_type", "")),
                    _md_escape(item.get("definition") or item.get("error") or item.get("suggested_role") or ""),
                ]
            )
            + " |"
        )
    lines.append("")

    filters = context.get("filters", [])
    if isinstance(filters, list) and filters:
        lines.append("## 筛选条件")
        lines.append("")
        lines.append("| key | Tableau字段 | 类型 | 说明 | 示例值 |")
        lines.append("|---|---|---|---|---|")
        for item in filters:
            if not isinstance(item, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_escape(item.get("key", "")),
                        _md_escape(item.get("tableau_field", "")),
                        _md_escape(item.get("kind", "")),
                        _md_escape(item.get("description", "")),
                        _md_escape(", ".join(str(x) for x in item.get("sample_values", []))),
                    ]
                )
                + " |"
            )
        lines.append("")

    unresolved_metrics = context.get("unresolved_metrics", [])
    unresolved_dimensions = context.get("unresolved_dimensions", [])
    if unresolved_metrics or unresolved_dimensions:
        lines.append("## 未完全解析项")
        lines.append("")
        if unresolved_metrics:
            lines.append(f"- 未完全解析指标：{', '.join(str(x) for x in unresolved_metrics)}")
        if unresolved_dimensions:
            lines.append(f"- 未完全解析维度：{', '.join(str(x) for x in unresolved_dimensions)}")
        lines.append("")

    lines.append("## 注入建议")
    lines.append("")
    lines.append("- 分析时优先使用已映射的标准指标/维度定义；未解析项不得静默替换口径。")
    lines.append("- 若源字段是子集口径、对比口径或本期/上期口径，必须保留源字段名，不要直接改写成总口径。")
    lines.append("- 若出现角色疑似不符（metric/dimension），以源字段原名为准，并在报告里显式披露。")
    lines.append("")
    return "\n".join(lines)


def write_source_context_bundle(output_dir: Path, context: dict[str, Any]) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "source_context.json"
    md_path = output_dir / "context_injection.md"
    json_path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_context_markdown(context), encoding="utf-8")
    return {
        "source_context_path": str(json_path.relative_to(output_dir)),
        "context_injection_path": str(md_path.relative_to(output_dir)),
    }
