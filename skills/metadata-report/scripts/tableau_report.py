#!/usr/bin/env python3
"""Internal Tableau metadata report renderer."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

load_dotenv(find_dotenv(usecwd=True))
load_dotenv(os.path.join(WORKSPACE_DIR, ".env"))

from runtime.tableau.source_context import build_source_context  # noqa: E402
from runtime.tableau.sqlite_store import list_entries, load_spec_by_entry_key  # noqa: E402
from skills.metadata.lib.metadata_io import (  # noqa: E402
    MetadataError,
    load_dataset_file,
    load_mapping_file,
    normalize_dataset,
    resolve_dataset_path,
)
from skills.metadata.lib.value_patterns import infer_value_pattern  # noqa: E402


def default_report_dir() -> Path:
    return WORKSPACE_DIR / "metadata" / "sync" / "tableau" / "reports"


def build_report_filename(source_id: str, *, generated_at: datetime) -> str:
    timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{source_id}_metadata_report.md"


def _load_targets(*, key: str | None, all_entries: bool) -> list[dict[str, Any]]:
    entries = [e for e in list_entries(active_only=not all_entries) if isinstance(e, dict)]
    if key:
        return [e for e in entries if e.get("key") == key]
    if all_entries:
        return entries
    return []


def _safe_list_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [x for x in value if isinstance(x, dict)]


def _safe_list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x) for x in value if isinstance(x, str) and x]


def _safe_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _display(value: Any) -> str:
    if value in (None, ""):
        return "未配置"
    if isinstance(value, list):
        return "、".join(str(item) for item in value) if value else "未配置"
    return str(value)


def _cell(value: Any) -> str:
    return _display(value).replace("|", "\\|").replace("\n", " ")


def _code(value: Any) -> str:
    return f"`{_cell(value).replace('`', '')}`"


def _load_yaml_dataset_if_exists(source_id: str) -> dict[str, Any] | None:
    if not source_id:
        return None
    try:
        path = resolve_dataset_path(WORKSPACE_DIR, source_id)
        return normalize_dataset(load_dataset_file(path), path=path)
    except MetadataError:
        return None


def _load_mapping_for_dataset(dataset: dict[str, Any] | None) -> dict[str, Any] | None:
    if not dataset:
        return None
    mapping_ref = str(dataset.get("mapping_ref") or "").strip()
    dataset_id = str(dataset.get("id") or dataset.get("source_id") or "").strip()
    candidates = []
    if mapping_ref:
        candidates.append(WORKSPACE_DIR / "metadata" / "mappings" / f"{mapping_ref}.yaml")
    if dataset_id:
        candidates.append(WORKSPACE_DIR / "metadata" / "mappings" / f"{dataset_id}.mapping.yaml")
    for path in candidates:
        if path.exists():
            try:
                return load_mapping_file(path)
            except MetadataError:
                return None
    return None


def _definition(item: dict[str, Any]) -> dict[str, Any]:
    return _safe_mapping(item.get("business_definition"))


def _is_pending_definition(item: dict[str, Any]) -> bool:
    definition = _definition(item)
    return (
        definition.get("needs_review") is True
        or item.get("review_required") is True
        or definition.get("source_type") == "pending"
    )


def _definition_text(item: dict[str, Any]) -> str:
    if _is_pending_definition(item):
        return "业务定义待确认"
    definition = _definition(item)
    return str(definition.get("text") or item.get("description") or "业务定义待确认")


def _definition_source(item: dict[str, Any]) -> str:
    if _is_pending_definition(item):
        return "pending"
    return str(_definition(item).get("source_type") or "未配置")


def _evidence_cell(item: dict[str, Any]) -> str:
    definition = _definition(item)
    evidence = _safe_list_dicts(definition.get("source_evidence"))
    sources = [str(x.get("source") or "").strip() for x in evidence if x.get("source")]
    return "<br>".join(sources) if sources else "未配置"


def _source_label(source: str) -> str:
    if source.startswith("column_name:"):
        return "字段名证据"
    if source.startswith("metric_expression:"):
        return "指标表达式"
    if source.startswith("source_field:"):
        return "来源字段"
    if source.startswith("metadata/sources/refine/"):
        return "样本画像"
    if "raw_20260430" in source or "指标卡" in source or "术语" in source:
        return "业务字典"
    if "配置定义抽取" in source:
        return "配置定义抽取"
    if "tableau" in source.lower():
        return "Tableau 素材"
    if source.startswith("duckdb.") or source.startswith("tableau."):
        return "mapping"
    return Path(source).name or source


def _review_source_text(item: dict[str, Any]) -> str:
    definition = _definition(item)
    evidence = _safe_list_dicts(definition.get("source_evidence"))
    labels: list[str] = []
    for record in evidence:
        source = str(record.get("source") or "").strip()
        if not source:
            continue
        label = _source_label(source)
        if label and label not in labels:
            labels.append(label)
    return "、".join(labels[:3]) if labels else "来源未配置"


def _review_text(item: dict[str, Any]) -> str:
    definition = _definition(item)
    source_text = _review_source_text(item)
    if _is_pending_definition(item):
        return f"待确认：{source_text}；需补业务定义"
    return f"已确认：{source_text}" if definition else "未配置"


def _field_source_name(field: dict[str, Any]) -> str:
    return str(field.get("source_field") or field.get("physical_name") or field.get("name") or "")


def _metric_source_name(metric: dict[str, Any]) -> str:
    source_mapping = _safe_mapping(metric.get("source_mapping"))
    return str(metric.get("source_field") or source_mapping.get("view_field") or metric.get("expression") or metric.get("name") or "")


def _metric_expression(metric: dict[str, Any]) -> str:
    return str(metric.get("expression") or f"source_field:{_metric_source_name(metric)}").replace("`", "")


def _mapping_note(row: dict[str, Any]) -> str:
    note = str(row.get("definition_override") or row.get("notes") or "").strip()
    if not note:
        return "未配置"
    if "待确认" in note or "需确认" in note or note.startswith("当前 Tableau 视图中的"):
        return "业务定义待确认"
    return note


def _page_url(entry: dict[str, Any]) -> str:
    base_url = str(os.environ.get("TABLEAU_BASE_URL", "")).rstrip("/")
    content_url = str((entry.get("tableau") or {}).get("content_url") or "").strip("/")
    if not base_url or not content_url or "/sheets/" not in content_url:
        return ""
    workbook_part, view_part = content_url.split("/sheets/", 1)
    if not workbook_part or not view_part:
        return ""
    return f"{base_url}/#/views/{workbook_part}/{view_part}"


def _default_date_examples(spec: dict[str, Any], generated_at: datetime) -> tuple[str, str]:
    sample_candidates: list[str] = []
    for item in _safe_list_dicts(spec.get("filters")) + _safe_list_dicts(spec.get("dimensions")):
        for sample in _safe_list_str(item.get("sample_values")):
            sample_candidates.append(sample)

    for sample in sample_candidates:
        match = re.match(r"^(\d{4}-\d{2}-\d{2})\|(\d{4}-\d{2}-\d{2})$", sample)
        if match:
            return match.group(1), match.group(2)

    start = generated_at.replace(day=1).strftime("%Y-%m-%d")
    end = generated_at.strftime("%Y-%m-%d")
    return start, end


def _description_suggestion(entry: dict[str, Any], spec: dict[str, Any], context: dict[str, Any]) -> str:
    existing = str(entry.get("description") or "").strip()
    if existing:
        return existing

    dims = _safe_list_str((entry.get("semantics") or {}).get("primary_dimensions"))[:3]
    metrics = _safe_list_str((entry.get("semantics") or {}).get("available_metrics"))[:4]
    params = [str(x.get("tableau_field")) for x in _safe_list_dicts(spec.get("parameters")) if x.get("tableau_field")]
    category = str(entry.get("category") or "业务")
    dimension_text = "、".join(dims) if dims else "核心维度"
    metric_text = "、".join(metrics) if metrics else "核心指标"
    param_text = "、".join(params) if params else "筛选条件"
    source_type = "视图" if entry.get("type") == "view" else "数据域"

    return (
        f"用于按{dimension_text}观察{category}相关表现的 Tableau {source_type}。"
        f"当前可分析 {metric_text} 等指标；支持通过 {param_text} 控制查询条件。"
    )


def _dimension_rows(spec: dict[str, Any], context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_name = {
        str(item.get("source_field")): item
        for item in _safe_list_dicts(context.get("dimensions"))
        if item.get("source_field")
    }
    rows: dict[str, dict[str, Any]] = {}
    for item in _safe_list_dicts(spec.get("dimensions")):
        name = str(item.get("name") or "")
        if not name:
            continue
        rows[name] = {
            "name": name,
            "data_type": item.get("data_type", ""),
            "sample_values": _safe_list_str(item.get("sample_values")),
            "status": str(by_name.get(name, {}).get("status", "unresolved")),
            "explanation": "",
            "source": "字段名推断",
        }
    return rows


def _metric_rows(spec: dict[str, Any], context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_name = {
        str(item.get("source_field")): item
        for item in _safe_list_dicts(context.get("metrics"))
        if item.get("source_field")
    }
    rows: dict[str, dict[str, Any]] = {}
    for item in _safe_list_dicts(spec.get("measures")):
        name = str(item.get("name") or "")
        ctx = by_name.get(name, {})
        if not name:
            continue
        rows[name] = {
            "name": name,
            "data_type": item.get("data_type", ""),
            "status": str(ctx.get("status", "unresolved")),
            "metric_id": str(ctx.get("metric_id", "")),
            "name_cn": str(ctx.get("name_cn", "")),
            "unit": str(ctx.get("unit", "")),
            "definition": str(ctx.get("definition") or ""),
        }
    return rows


def _dimension_explanation(name: str, row: dict[str, Any]) -> str:
    if name == "Airline*":
        return "公司代码字段，表示市场中的承运公司"
    if name == "Completesegment":
        return "完整产品或市场单元字段，用于表示当前分析对象的业务组合"
    if name == "数据参考列":
        return "当前数据覆盖时间窗的参考串，常见形态为 开始日期|结束日期"
    if name == "是否在开始日期和结束日期之间":
        return "由日期参数驱动的布尔标识，表示记录是否落在设定时间窗内"
    return ""


def _format_sample_cell(values: list[str]) -> str:
    if not values:
        return "无"
    pattern = infer_value_pattern(values)
    if pattern:
        return f"{pattern['example']}（正则：`{pattern['regex']}`）"
    return "、".join(values[:5])


def _short_list(values: list[str], *, limit: int = 3, fallback: str = "未配置") -> str:
    clean_values = [value for value in values if value]
    if not clean_values:
        return fallback
    suffix = f" 等 {len(clean_values)} 项" if len(clean_values) > limit else ""
    return "、".join(clean_values[:limit]) + suffix


def _definition_status(item: dict[str, Any]) -> str:
    if _is_pending_definition(item):
        return "待确认"
    if _definition(item):
        return "已确认"
    return "仅结构可用"


def _field_kind(field: dict[str, Any]) -> str:
    role = str(field.get("role") or "")
    if role == "time_dimension":
        return "时间"
    if role == "dimension":
        return "维度"
    if role in {"metric_source", "measure_candidate"}:
        return "指标来源"
    return "属性"


def _field_usage(field: dict[str, Any]) -> str:
    role = str(field.get("role") or "")
    if role == "time_dimension":
        return "用于时间筛选和趋势分析"
    if role == "dimension":
        return "用于筛选、分组和下钻"
    if role in {"metric_source", "measure_candidate"}:
        return "用于指标计算或汇总"
    return "用于补充识别记录"


def _source_summary_cell(item: dict[str, Any]) -> str:
    source_text = _review_source_text(item)
    if source_text == "来源未配置":
        return _definition_source(item)
    return source_text


def _parse_export_payload(path_value: str | None) -> dict[str, Any] | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _export_section(
    *,
    entry: dict[str, Any],
    export_summary: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
) -> list[str]:
    """Return detail lines to embed under section 9.4 when export data is available."""
    lines: list[str] = []
    if not export_summary:
        return lines

    page_url = str((((export_summary.get("views") or [None])[0]) or {}).get("tableau", {}).get("page_url") or _page_url(entry))
    lines.append("#### Tableau 导出执行结果")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    lines.append("| 验证入口 | `export_source.py` |")
    lines.append(f"| 导出状态 | {'成功' if export_summary.get('success') else '失败'} |")
    lines.append(f"| 导出时间 | `{export_summary.get('timestamp', '')}` |")
    view0 = ((export_summary.get("views") or [None])[0]) or {}
    lines.append(f"| 导出文件 | `{view0.get('file_path', '')}` |")
    lines.append("| `export_summary.json` | 已提供 |")
    lines.append(f"| `manifest` | {'已提供' if manifest else '未提供'} |")
    if manifest:
        lines.append(f"| 导出行数 | `{manifest.get('row_count', '')}` |")
        columns = (((manifest.get("schema") or {}).get("columns")) or [])
        lines.append(f"| 导出列数 | `{len(columns)}` |")
    if page_url:
        lines.append(f"| 页面地址 | `{page_url}` |")
    lines.append("")

    if manifest:
        lines.append("#### 实际导出物理列")
        lines.append("")
        for index, column in enumerate((((manifest.get("schema") or {}).get("columns")) or []), start=1):
            if not isinstance(column, dict):
                continue
            lines.append(f"{index}. `{column.get('name', '')}`")
        lines.append("")

        _spec = load_spec_by_entry_key(str(entry.get("key"))) or {}
        logical_count = len(_safe_list_dicts(_spec.get("dimensions"))) + len(_safe_list_dicts(_spec.get("measures")))
        physical_count = len((((manifest.get("schema") or {}).get("columns")) or []))
        if logical_count and physical_count and logical_count != physical_count:
            lines.append("#### 结构差异说明")
            lines.append("")
            lines.append("这条数据源存在“逻辑字段 vs 物理列”差异：")
            lines.append("")
            lines.append(f"- registry/spec 中逻辑可用字段共 `{logical_count}` 个")
            lines.append(f"- 实际导出的 CSV 物理列共 `{physical_count}` 个")
            lines.append("- 这通常意味着部分业务指标通过 `度量名称` / `度量值` 以长表方式表达，而不是宽表独立列")
            lines.append("- 后续分析前应先核对这份元数据报告或 `export_summary.json`，确认当前导出是宽表还是长表")
            lines.append("")

    return lines


def render_sync_report(
    *,
    entry: dict[str, Any],
    spec: dict[str, Any],
    context: dict[str, Any],
    generated_at: datetime,
    report_dir: Path,
    with_samples: bool,
    sync_mode: str,
    step_results: dict[str, str],
    export_summary: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
) -> str:
    semantics = entry.get("semantics") if isinstance(entry.get("semantics"), dict) else {}
    filters = _safe_list_dicts(spec.get("filters"))
    params = _safe_list_dicts(spec.get("parameters"))
    dims = _safe_list_dicts(spec.get("dimensions"))
    meas = _safe_list_dicts(spec.get("measures"))
    dataset = _load_yaml_dataset_if_exists(str(entry.get("source_id") or ""))
    mapping = _load_mapping_for_dataset(dataset)
    business = _safe_mapping(dataset.get("business")) if dataset else {}
    maintenance = _safe_mapping(dataset.get("maintenance")) if dataset else {}
    yaml_fields = _safe_list_dicts(dataset.get("fields")) if dataset else []
    yaml_metrics = _safe_list_dicts(dataset.get("metrics")) if dataset else []
    mapping_rows = _safe_list_dicts(_safe_mapping(mapping).get("mappings")) if mapping else []
    description_notes = _safe_list_dicts(spec.get("description_notes"))
    unresolved_dimensions = _safe_list_str(context.get("unresolved_dimensions"))
    start_date, end_date = _default_date_examples(spec, generated_at)
    pending_questions = _safe_list_str(maintenance.get("pending_questions"))
    review_fields = [field for field in yaml_fields if _is_pending_definition(field)]
    review_metrics = [metric for metric in yaml_metrics if _is_pending_definition(metric)]

    display_name = _cell((dataset or {}).get("display_name") or entry.get("display_name") or "Tableau 数据源")
    page_url = _page_url(entry)
    tableau = entry.get("tableau") if isinstance(entry.get("tableau"), dict) else {}
    dimension_rows = _dimension_rows(spec, context)
    metric_rows = _metric_rows(spec, context)
    semantic_grain = _safe_list_str(business.get("grain")) or _safe_list_str(semantics.get("grain"))
    suitable_for = _safe_list_str(business.get("suitable_for")) or _safe_list_str(semantics.get("suitable_for"))
    not_suitable_for = _safe_list_str(business.get("not_suitable_for")) or _safe_list_str(semantics.get("not_suitable_for"))
    description_text = (dataset or {}).get("description") or business.get("description") or _description_suggestion(entry, spec, context)
    field_count = len(yaml_fields) or len(dims) + len(meas)
    metric_count = len(yaml_metrics) or len(meas)
    review_count = len(review_fields) + len(review_metrics)
    export_status = "已验证成功" if export_summary and export_summary.get("success") else "验证失败" if export_summary else "未执行导出验证"
    missing_validation = [
        str(item.get("tableau_field") or item.get("key") or "")
        for item in filters + params
        if not (item.get("validation") if isinstance(item.get("validation"), dict) else {})
    ]
    if review_count or pending_questions:
        ready_status = "可用但有待确认"
        primary_risk = "存在待确认字段或指标，相关口径不能直接用于正式结论"
    elif not dataset:
        ready_status = "可用但缺少业务 metadata"
        primary_risk = "未找到 metadata YAML，当前仅能说明 Tableau 运行入口和字段结构"
    elif export_summary and not export_summary.get("success"):
        ready_status = "暂不建议用于正式分析"
        primary_risk = "Tableau 导出验证失败，需要先修复导出链路"
    else:
        ready_status = "可用"
        primary_risk = "Tableau 页面可见字段不一定等同于导出物理列"

    lines: list[str] = []
    lines.append(f"# {display_name} 元数据报告")
    lines.append("")
    lines.append("## 1. 数据源结论")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("| --- | --- |")
    lines.append(f"| 数据源 | {display_name} |")
    lines.append(f"| 数据类型 | Tableau / {_cell(entry.get('type') or 'view')} |")
    lines.append(f"| 当前状态 | {ready_status} |")
    lines.append(f"| 数据规模 | {field_count} 个字段，{metric_count} 个指标，{len(filters)} 个筛选器，{len(params)} 个参数 |")
    lines.append(f"| 主要用途 | {_cell(_short_list(suitable_for))} |")
    lines.append(f"| 不能用于 | {_cell(_short_list(not_suitable_for))} |")
    lines.append(f"| 最大风险 | {_cell(primary_risk)} |")
    lines.append(f"| 待确认项 | {len(review_fields)} 个字段，{len(review_metrics)} 个指标 |")
    lines.append("")
    lines.append("本报告说明这份 Tableau 数据源的 metadata 设计、字段和指标口径、筛选器、参数、导出边界和待确认问题。它不输出经营分析结论，只说明这份数据能怎样被可靠使用。")
    lines.append("")

    lines.append("## 2. 业务适用场景")
    lines.append("")
    lines.append("### 2.1 可以直接支持")
    lines.append("")
    if suitable_for:
        lines.append("| 场景 | 可用依据 | 使用提醒 |")
        lines.append("| --- | --- | --- |")
        basis = f"{field_count} 个字段、{metric_count} 个指标、{len(filters)} 个筛选器、{len(params)} 个参数"
        for item in suitable_for:
            lines.append(f"| {_cell(item)} | {_cell(basis)} | 先确认第 4 章筛选器/参数，再执行导出。 |")
    else:
        lines.append("- 未配置明确适用场景。")
    lines.append("")
    lines.append("### 2.2 可以使用，但需要先确认口径")
    lines.append("")
    if review_fields or review_metrics or pending_questions:
        lines.append("| 场景 | 当前缺口 | 确认后可支持什么 |")
        lines.append("| --- | --- | --- |")
        for metric in review_metrics[:10]:
            lines.append(f"| {_cell(metric.get('display_name') or metric.get('name'))} 相关分析 | 指标业务定义待确认 | 可作为确定指标进入正式分析口径。 |")
        for field in review_fields[:10]:
            lines.append(f"| {_cell(field.get('display_name') or field.get('name'))} 相关筛选或分组 | 字段业务定义待确认 | 可作为稳定维度进入分析上下文。 |")
        for question in pending_questions[:10]:
            lines.append(f"| 待确认主题 | {_cell(question)} | 明确后可补齐字段、指标或边界说明。 |")
    else:
        lines.append("- 当前没有显式待确认字段或指标。")
    lines.append("")
    lines.append("### 2.3 不建议用于")
    lines.append("")
    if not_suitable_for:
        lines.append("| 场景 | 原因 |")
        lines.append("| --- | --- |")
        for item in not_suitable_for:
            lines.append(f"| {_cell(item)} | 当前 metadata 已标记为不适用场景。 |")
    else:
        lines.append("- 未配置不适用场景；正式分析前仍需核对视图口径和导出字段。")
    lines.append("")

    lines.append("## 3. 核心字段与指标速查")
    lines.append("")
    lines.append("### 3.1 常用字段")
    lines.append("")
    lines.append("| 名称 | 类型 | 业务含义 | 常见用途 | 口径状态 | 使用提醒 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    if yaml_fields:
        for field in yaml_fields[:20]:
            lines.append(
                f"| {_cell(field.get('display_name') or field.get('name'))} | {_cell(_field_kind(field))} | "
                f"{_cell(_definition_text(field))} | {_cell(_field_usage(field))} | "
                f"{_cell(_definition_status(field))} | Tableau 导出字段需以验证结果为准。 |"
            )
    else:
        for name, row in list(dimension_rows.items())[:20]:
            explanation = _dimension_explanation(name, row) or "待补充维度定义"
            lines.append(f"| {_cell(name)} | 维度 | {_cell(explanation)} | 用于筛选、分组和下钻 | 待确认 | 来自 Tableau spec，建议补齐 metadata YAML。 |")
    lines.append("")
    lines.append("### 3.2 常用指标")
    lines.append("")
    if yaml_metrics or metric_rows:
        lines.append("| 指标 | 业务含义 | 计算或聚合方式 | 单位 | 适用粒度 | 口径状态 | 使用提醒 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        if yaml_metrics:
            for metric in yaml_metrics[:20]:
                aggregation = metric.get("aggregation") or _metric_expression(metric)
                lines.append(
                    f"| {_cell(metric.get('display_name') or metric.get('name'))} | {_cell(_definition_text(metric))} | "
                    f"{_cell(aggregation)} | {_cell(metric.get('unit'))} | {_cell(_short_list(semantic_grain))} | "
                    f"{_cell(_definition_status(metric))} | 待确认指标不能直接用于正式结论。 |"
                )
        else:
            for row in list(metric_rows.values())[:20]:
                lines.append(
                    f"| {_cell(row.get('name'))} | {_cell(row.get('definition') or '待补充指标定义')} | Tableau 视图字段 | "
                    f"{_cell(row.get('unit'))} | {_cell(_short_list(semantic_grain))} | 待确认 | 建议补齐 metadata YAML。 |"
                )
    else:
        lines.append("- 无指标。")
    lines.append("")

    lines.append("## 4. 筛选方式与常用入口")
    lines.append("")
    lines.append("| 筛选入口 | 类型 | 示例值/规则 | 使用方式 | 使用提醒 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in filters:
        field = str(item.get("tableau_field") or item.get("key") or "")
        values = _safe_list_str(item.get("sample_values"))
        sample_text = _format_sample_cell(values) if values else "未采集"
        lines.append(f"| {_cell(field)} | 筛选器 | {_cell(sample_text)} | `--vf` | 样例值不代表完整枚举。 |")
    for item in params:
        field = str(item.get("tableau_field") or item.get("key") or "")
        example_value = start_date if "开始" in field else end_date if "结束" in field else start_date
        lines.append(f"| {_cell(field)} | 参数 | {example_value} | `--vp` | 参数不能写成 `--vf`。 |")
    if not filters and not params:
        lines.append("| 未配置 | 未配置 | 未配置 | 未配置 | 当前未发现筛选器或参数。 |")
    lines.append("")
    lines.append("Tableau 筛选器必须使用 `--vf`，参数必须使用 `--vp`。页面可见值和 API 可筛选值可能不完全一致，正式导出前应看导出验证结果。")
    lines.append("")

    lines.append("## 5. 重点口径确认清单")
    lines.append("")
    if review_fields or review_metrics or pending_questions or unresolved_dimensions:
        lines.append("| 优先级 | 主题 | 影响 | 当前问题 | 建议确认对象/材料 | 确认后用途 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for metric in review_metrics:
            name = metric.get("display_name") or metric.get("name")
            lines.append(f"| 高 | {_cell(name)} | 影响指标解释和汇总口径 | 业务定义待确认 | 业务字典或指标负责人 | 可进入正式指标口径。 |")
        for field in review_fields:
            name = field.get("display_name") or field.get("name")
            lines.append(f"| 中 | {_cell(name)} | 影响筛选、分组或字段解释 | 业务定义待确认 | 数据源 owner 或口径文档 | 可作为稳定维度使用。 |")
        for name in unresolved_dimensions:
            lines.append(f"| 中 | {_cell(name)} | 影响标准语义匹配 | 尚未标准化维度 | metadata 维护人员 | 可进入统一语义层。 |")
        for question in pending_questions:
            lines.append(f"| 中 | 待确认主题 | 影响 metadata 完整性 | {_cell(question)} | 数据源 owner 或业务口径材料 | 补齐报告边界和使用说明。 |")
    else:
        lines.append("- 无显式待确认字段或指标。")
    lines.append("")

    lines.append("## 6. 数据边界与风险")
    lines.append("")
    lines.append("| 边界/风险 | 说明 | 对使用者的影响 |")
    lines.append("| --- | --- | --- |")
    lines.append(f"| 视图口径 | {_cell(description_text)} | 只能按当前 Tableau 视图口径解释数据。 |")
    lines.append(f"| 导出验证 | {export_status} | 未验证时不能证明 CSV 已能稳定拉取。 |")
    lines.append("| 筛选值边界 | 筛选器样例值来自 discovery/sync 素材 | 不能当作完整枚举清单。 |")
    lines.append("| 字段边界 | Tableau 页面可见字段和导出物理列可能不同 | 后续分析前应核对 manifest 或 export_summary。 |")
    if missing_validation:
        lines.append(f"| validation 缺口 | {_cell(_short_list(missing_validation, limit=5))} 未固化 validation 对象 | 需要补齐后再作为稳定导出入口。 |")
    if description_notes:
        lines.append(f"| 计算字段说明 | 当前 spec 含 {len(description_notes)} 条补充说明 | 可在完整明细和源材料中复核。 |")
    lines.append("")

    lines.append("## 7. 完整字段与指标明细")
    lines.append("")
    lines.append("### 7.1 字段明细")
    lines.append("")
    lines.append("| 名称 | 源字段 | 类型 | 角色 | 业务定义 | 示例/规则 | 口径状态 | 来源摘要 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    if yaml_fields:
        tableau_type_by_name = {
            str(item.get("name") or ""): str(item.get("data_type") or "")
            for item in [*dims, *meas]
            if item.get("name")
        }
        for field in yaml_fields:
            source_field = _field_source_name(field)
            sample_text = _format_sample_cell(_safe_list_str(_safe_mapping(field).get("sample_values")))
            lines.append(
                f"| {_cell(field.get('display_name') or field.get('name'))} | {_code(source_field)} | "
                f"{_code(tableau_type_by_name.get(source_field) or field.get('type'))} | {_code(field.get('role'))} | "
                f"{_cell(_definition_text(field))} | {_cell(sample_text)} | {_cell(_definition_status(field))} | {_cell(_source_summary_cell(field))} |"
            )
    else:
        for name, row in dimension_rows.items():
            explanation = _dimension_explanation(name, row) or "待补充维度定义"
            sample_values = _format_sample_cell(_safe_list_str(row.get("sample_values")))
            lines.append(f"| {_cell(name)} | {_code(name)} | {_code(row.get('data_type'))} | `dimension` | {_cell(explanation)} | {_cell(sample_values)} | 待确认 | 字段名推断 |")
    lines.append("")
    lines.append("### 7.2 指标明细")
    lines.append("")
    if yaml_metrics or metric_rows:
        lines.append("| 指标 | 源字段/表达式 | 聚合方式 | 单位 | 业务定义 | 适用粒度 | 口径状态 | 来源摘要 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        if yaml_metrics:
            for metric in yaml_metrics:
                lines.append(
                    f"| {_cell(metric.get('display_name') or metric.get('name'))} | {_code(_metric_expression(metric))} | "
                    f"{_code(metric.get('aggregation'))} | {_code(metric.get('unit'))} | {_cell(_definition_text(metric))} | "
                    f"{_cell(_short_list(semantic_grain))} | {_cell(_definition_status(metric))} | {_cell(_source_summary_cell(metric))} |"
                )
        else:
            for row in metric_rows.values():
                lines.append(
                    f"| {_cell(row.get('name'))} | {_code(row.get('name'))} | Tableau 视图字段 | {_code(row.get('unit'))} | "
                    f"{_cell(row.get('definition') or '待补充指标定义')} | {_cell(_short_list(semantic_grain))} | 待确认 | 标准映射 |"
                )
    else:
        lines.append("- 无指标。")
    lines.append("")
    lines.append("### 7.3 筛选器/参数明细")
    lines.append("")
    lines.append("| 名称 | 类型 | 字段/参数 | 可选值/规则 | 是否必填 | 口径状态 | 来源摘要 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for item in filters:
        field = str(item.get("tableau_field") or item.get("key") or "")
        values = _safe_list_str(item.get("sample_values"))
        sample_text = _format_sample_cell(values) if values else "未采集"
        lines.append(f"| {_cell(field)} | 筛选器 | {_code(field)} | {_cell(sample_text)} | 否 | 仅结构可用 | Tableau spec |")
    for item in params:
        field = str(item.get("tableau_field") or item.get("key") or "")
        lines.append(f"| {_cell(field)} | 参数 | {_code(field)} | YYYY-MM-DD | 视参数而定 | 仅结构可用 | Tableau spec |")
    if not filters and not params:
        lines.append("| 未配置 | 未配置 | 未配置 | 未配置 | 未配置 | 未配置 | 未配置 |")
    lines.append("")

    lines.append("## 8. Connector 使用说明")
    lines.append("")
    lines.append("### 8.1 DuckDB 使用说明")
    lines.append("")
    lines.append("- 无。该报告为 Tableau 数据源报告。")
    lines.append("")
    lines.append("### 8.2 Tableau 使用说明")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    lines.append(f"| Workbook | {_cell(tableau.get('workbook_name') or '空字符串，当前 Tableau API 未返回名称')} |")
    lines.append(f"| View | {_cell(tableau.get('view_name'))} |")
    lines.append(f"| View LUID | {_code(tableau.get('view_luid'))} |")
    lines.append(f"| Content URL | {_code(tableau.get('content_url'))} |")
    if page_url:
        lines.append(f"| 页面 URL | {_code(page_url)} |")
    lines.append(f"| 导出验证 | {export_status} |")
    lines.append("")
    lines.append("| 类型 | 名称 | 示例 | 用途 |")
    lines.append("| --- | --- | --- | --- |")
    for item in filters[:20]:
        field = str(item.get("tableau_field") or item.get("key") or "")
        values = _safe_list_str(item.get("sample_values"))
        value = values[0] if values else "<value>"
        lines.append(f"| 筛选器 | {_cell(field)} | `--vf \"{field}={value}\"` | 控制 Tableau 视图筛选。 |")
    for item in params:
        field = str(item.get("tableau_field") or item.get("key") or "")
        value = start_date if "开始" in field else end_date if "结束" in field else start_date
        lines.append(f"| 参数 | {_cell(field)} | `--vp \"{field}={value}\"` | 控制 Tableau 参数。 |")
    lines.append("")
    lines.append("推荐导出命令：")
    lines.append("")
    lines.append("```bash")
    command_lines = [
        f'python3 {WORKSPACE_DIR / ".agents" / "skills" / "tableau" / "scripts" / "export_source.py"}',
        f'  --source-id {entry.get("source_id", "")}',
    ]
    for item in params:
        field = str(item.get("tableau_field") or item.get("key") or "")
        value = start_date if "开始" in field else end_date if "结束" in field else start_date
        command_lines.append(f'  --vp "{field}={value}"')
    if filters:
        filter_item = filters[0]
        filter_field = str(filter_item.get("tableau_field") or filter_item.get("key") or "")
        filter_values = _safe_list_str(filter_item.get("sample_values"))
        value = filter_values[0] if filter_values else "<value>"
        command_lines.append(f'  --vf "{filter_field}={value}"')
    for index, line in enumerate(command_lines):
        suffix = " \\" if index < len(command_lines) - 1 else ""
        lines.append(line + suffix)
    lines.append("```")
    lines.append("")

    lines.append("## 9. 技术维护附录")
    lines.append("")
    lines.append("### 9.1 注册与生成信息")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    chain_steps = ["register"] if not spec else []
    chain_steps.extend(["sync_fields", "sync_filters"])
    if step_results.get("registry") != "skipped":
        chain_steps.append("sync_registry")
    rows = [
        ("source_id / dataset_id", entry.get("source_id")),
        ("key", entry.get("key")),
        ("type", entry.get("type")),
        ("status", entry.get("status")),
        ("category", entry.get("category")),
        ("mapping_ref", (dataset or {}).get("mapping_ref")),
        ("报告生成时间", generated_at.strftime("%Y-%m-%d %H:%M:%S")),
        ("默认报告目录", str(report_dir)),
        ("执行链路", " -> ".join(chain_steps)),
        ("步骤状态", f"fields={step_results.get('fields', 'unknown')}, filters={step_results.get('filters', 'unknown')}, registry={step_results.get('registry', 'unknown')}"),
    ]
    for key, value in rows:
        lines.append(f"| `{_cell(key)}` | {_code(value)} |")
    lines.append("")
    lines.append("### 9.2 Metadata 来源")
    lines.append("")
    lines.append("| 来源 | 用途 | 状态 |")
    lines.append("| --- | --- | --- |")
    lines.append(f"| `metadata/datasets/*.yaml` | 数据集、字段、指标、粒度和适用边界 | {'已读取' if dataset else '未找到'} |")
    lines.append(f"| `metadata/mappings/*.yaml` | 源字段到标准语义的映射和 review 状态 | {'已读取' if mapping_rows else '未配置'} |")
    lines.append("| `metadata/dictionaries/*.yaml` | 公共指标、维度和术语定义 | 通过 definition source 间接引用 |")
    lines.append("| Tableau runtime spec | 筛选器、参数、字段结构 | 已读取 |")
    lines.append(f"| export manifest | 导出物理列和行列数 | {'已提供' if manifest else '未提供'} |")
    lines.append("")
    lines.append("### 9.3 映射明细")
    lines.append("")
    if mapping_rows:
        lines.append("| 源字段 | 类型 | 标准 ID | 字段 ID/覆盖 | 维护说明 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in mapping_rows:
            lines.append(
                f"| {_code(row.get('view_field'))} | {_code(row.get('type'))} | "
                f"{_code(row.get('standard_id'))} | {_code(row.get('field_id_or_override'))} | {_cell(_mapping_note(row))} |"
            )
    else:
        lines.append("- 待补充映射。")
    lines.append("")
    lines.append("### 9.4 校验结果")
    lines.append("")
    lines.append("| 校验项 | 结果 | 说明 |")
    lines.append("| --- | --- | --- |")
    lines.append(f"| Tableau 导出 | {export_status} | {'已提供导出结果。' if export_summary else '未执行正式 CSV 导出验证。'} |")
    lines.append(f"| manifest | {'已提供' if manifest else '未提供'} | 用于核对实际导出物理列。 |")
    lines.append(f"| metadata YAML | {'已读取' if dataset else '未找到'} | 未找到时只说明运行结构，不作为完整业务口径。 |")
    lines.append("")
    lines.extend(_export_section(entry=entry, export_summary=export_summary, manifest=manifest))

    lines.append("## 10. 结论")
    lines.append("")
    lines.append(f"- 这份 Tableau metadata 当前状态：{ready_status}。")
    lines.append(f"- 可以优先用于：{_short_list(suitable_for)}。")
    lines.append(f"- 暂不应用于：{_short_list(not_suitable_for)}。")
    if review_fields or review_metrics:
        top_reviews = [str(item.get("display_name") or item.get("name")) for item in [*review_metrics, *review_fields]][:5]
        lines.append(f"- 下一步需要确认：{_short_list(top_reviews, limit=5)}。")
    elif pending_questions:
        lines.append(f"- 下一步需要确认：{_short_list(pending_questions, limit=3)}。")
    else:
        lines.append("- 下一步需要确认：无显式待确认项。")
    return "\n".join(lines).rstrip() + "\n"


def write_report(
    *,
    entry: dict[str, Any],
    spec: dict[str, Any],
    context: dict[str, Any],
    report_dir: Path,
    generated_at: datetime,
    with_samples: bool,
    sync_mode: str,
    step_results: dict[str, str],
    export_summary: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    filename = build_report_filename(str(entry.get("source_id") or entry.get("key") or "unknown"), generated_at=generated_at)
    report_path = report_dir / filename
    markdown = render_sync_report(
        entry=entry,
        spec=spec,
        context=context,
        generated_at=generated_at,
        report_dir=report_dir,
        with_samples=with_samples,
        sync_mode=sync_mode,
        step_results=step_results,
        export_summary=export_summary,
        manifest=manifest,
    )
    report_path.write_text(markdown, encoding="utf-8")
    return report_path


def main() -> None:
    print(
        "[Error] tableau_report.py is an internal renderer. "
        "Use skills/metadata-report/scripts/generate_report.py --connector tableau ..."
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
