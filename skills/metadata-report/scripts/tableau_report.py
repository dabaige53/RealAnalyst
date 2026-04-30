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
    return definition.get("needs_review") is True or item.get("review_required") is True


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


def _review_text(item: dict[str, Any]) -> str:
    definition = _definition(item)
    confidence = definition.get("confidence")
    confidence_text = f"（置信度 {confidence}）" if confidence is not None else ""
    if _is_pending_definition(item):
        return f"待确认{confidence_text}"
    return f"已通过{confidence_text}" if definition else "未配置"


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


def _render_filter_values(values: list[str]) -> list[str]:
    if not values:
        return ["- 当前未采到样例值"]
    pattern = infer_value_pattern(values)
    if pattern:
        return [f"- `{pattern['example']}`（正则：`{pattern['regex']}`）"]
    return [f"- `{value}`" for value in values]


def _format_sample_cell(values: list[str]) -> str:
    if not values:
        return "无"
    pattern = infer_value_pattern(values)
    if pattern:
        return f"{pattern['example']}（正则：`{pattern['regex']}`）"
    return "、".join(values[:5])


def _has_sample_values(items: list[dict[str, Any]]) -> bool:
    return any(_safe_list_str(item.get("sample_values")) for item in items)


def _usage_example_for_filter(filter_item: dict[str, Any]) -> str:
    field = str(filter_item.get("tableau_field") or filter_item.get("key") or "")
    values = _safe_list_str(filter_item.get("sample_values"))
    if not field:
        return ""
    if not values:
        return "不建议直接使用"
    return f'`--vf "{field}={values[0]}"`'


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
    lines: list[str] = []
    lines.append("## 10. 校验结果")
    lines.append("")

    if not export_summary:
        lines.append("- Tableau 正式 CSV 导出：未执行。")
        lines.append("- 本报告已覆盖 registry、spec、source_context 和 metadata YAML 同步结果，但不能证明 Tableau 数据已成功拉取。")
        lines.append("- `export_ready` 只表示具备后续导出条件，不等同于导出验证通过。")
        lines.append("")
        return lines

    page_url = str((((export_summary.get("views") or [None])[0]) or {}).get("tableau", {}).get("page_url") or _page_url(entry))
    lines.append("### 10.1 Tableau 导出执行结果")
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
        lines.append("### 10.2 实际导出物理列")
        lines.append("")
        for index, column in enumerate((((manifest.get("schema") or {}).get("columns")) or []), start=1):
            if not isinstance(column, dict):
                continue
            lines.append(f"{index}. `{column.get('name', '')}`")
        lines.append("")

        logical_count = len(_safe_list_dicts(load_spec_by_entry_key(str(entry.get("key"))) or {}.get("dimensions"))) + len(
            _safe_list_dicts(load_spec_by_entry_key(str(entry.get("key"))) or {}.get("measures"))
        )
        physical_count = len((((manifest.get("schema") or {}).get("columns")) or []))
        if logical_count and physical_count and logical_count != physical_count:
            lines.append("### 10.3 需要特别说明的结构差异")
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
    review_fields = [field for field in yaml_fields if _definition(field).get("needs_review") is True]
    review_metrics = [metric for metric in yaml_metrics if _definition(metric).get("needs_review") is True]

    lines: list[str] = []
    lines.append(f"# {_cell((dataset or {}).get('display_name') or entry.get('display_name') or 'Tableau Sync Report')} 注册报告")
    lines.append("")
    lines.append("## 1. 同步任务概览")
    lines.append("")
    lines.append("- 报告类型：Tableau 数据源同步明细报告")
    lines.append(f"- 报告生成时间：{generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 同步对象：`{entry.get('source_id', '')}`")
    lines.append(f"- 显示名称：`{(dataset or {}).get('display_name') or entry.get('display_name', '')}`")
    page_url = _page_url(entry)
    if page_url:
        lines.append(f"- 原始链接：`{page_url}`")
    lines.append(f"- 默认报告目录：`{report_dir}`")
    chain_steps = ["register"] if not spec else []
    chain_steps.extend(["sync_fields", "sync_filters"])
    if step_results.get("registry") != "skipped":
        chain_steps.append("sync_registry")
    lines.append("- 本次执行链路：" + " → ".join(f"`{x}`" for x in chain_steps))
    lines.append(f"- 同步模式：`{sync_mode}`")
    lines.append(f"- 是否采集样例值：{'是' if with_samples else '否'}")
    lines.append(
        "- 步骤状态："
        + f" fields={step_results.get('fields', 'unknown')},"
        + f" filters={step_results.get('filters', 'unknown')},"
        + f" registry={step_results.get('registry', 'unknown')}"
    )
    if dataset:
        lines.append("- metadata YAML：已读取，字段/指标定义优先来自 `metadata/datasets`")
    else:
        lines.append("- metadata YAML：未找到，本报告仅基于 runtime registry/spec")
    lines.append("")

    lines.append("## 2. 数据源注册信息")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    lines.append(f"| `source_id` | `{entry.get('source_id', '')}` |")
    lines.append(f"| `key` | `{entry.get('key', '')}` |")
    lines.append(f"| `display_name` | `{entry.get('display_name', '')}` |")
    lines.append(f"| `type` | `{entry.get('type', '')}` |")
    lines.append(f"| `status` | `{entry.get('status', '')}` |")
    lines.append(f"| `category` | `{entry.get('category', '')}` |")
    if dataset:
        lines.append(f"| `mapping_ref` | {_code(dataset.get('mapping_ref'))} |")
        evidence = _safe_list_dicts(maintenance.get("source_evidence"))
        source_evidence = "; ".join(str(item.get("source")) for item in evidence if item.get("source"))
        lines.append(f"| `source_evidence` | {_code(source_evidence or '未配置')} |")
    tableau = entry.get("tableau") if isinstance(entry.get("tableau"), dict) else {}
    lines.append(f"| `view_luid` | `{tableau.get('view_luid', '')}` |")
    lines.append(f"| `view_name` | `{tableau.get('view_name', '')}` |")
    lines.append(f"| `content_url` | `{tableau.get('content_url', '')}` |")
    if page_url:
        lines.append(f"| `page_url` | `{page_url}` |")
    lines.append(f"| `workbook_id` | `{tableau.get('workbook_id', '')}` |")
    lines.append(f"| `workbook_name` | `{tableau.get('workbook_name', '') or '空字符串，当前 Tableau API 未返回名称'}` |")
    lines.append(f"| `description` | {_code((dataset or {}).get('description') or business.get('description') or entry.get('description') or '当前 registry 内为空，尚未固化业务描述')} |")
    lines.append("")

    lines.append("## 3. 本次写入摘要")
    lines.append("")
    lines.append(f"- 字段总数：`{len(yaml_fields) or len(dims) + len(meas)}`")
    lines.append(f"- 维度数：`{len(dims)}`")
    lines.append(f"- 指标数：`{len(yaml_metrics) or len(meas)}`")
    lines.append(f"- 筛选器数：`{len(filters)}`")
    lines.append(f"- 参数数：`{len(params)}`")
    if dataset:
        lines.append(f"- mapping 条目数：`{len(mapping_rows)}`")
        lines.append(f"- 待确认字段数：`{len(review_fields)}`")
        lines.append(f"- 待确认指标数：`{len(review_metrics)}`")
    lines.append(f"- 筛选器样例值状态：{'已采集' if _has_sample_values(filters) else '未采集'}")
    missing_validation = [
        (item.get("tableau_field") or item.get("key") or "")
        for item in filters + params
        if not (item.get("validation") if isinstance(item.get("validation"), dict) else {})
    ]
    if missing_validation:
        lines.append("- 未固化 validation 对象：" + "、".join(f"`{name}`" for name in missing_validation if name))
    lines.append("")

    lines.append("## 4. 语义层明细")
    lines.append("")
    lines.append("### 4.1 业务描述")
    lines.append("")
    description_text = (dataset or {}).get("description") or business.get("description") or _description_suggestion(entry, spec, context)
    lines.append(f"> {description_text}")
    lines.append("")

    semantic_grain = _safe_list_str(business.get("grain")) or _safe_list_str(semantics.get("grain"))
    semantic_time_fields = _safe_list_str(business.get("time_fields")) or _safe_list_str(semantics.get("time_fields"))
    suitable_for = _safe_list_str(business.get("suitable_for")) or _safe_list_str(semantics.get("suitable_for"))
    not_suitable_for = _safe_list_str(business.get("not_suitable_for")) or _safe_list_str(semantics.get("not_suitable_for"))
    lines.append("### 4.2 粒度")
    lines.append("")
    for item in semantic_grain or ["未配置"]:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("### 4.3 时间字段 / 参数")
    lines.append("")
    for item in semantic_time_fields or [str(param.get("tableau_field") or param.get("key") or "") for param in params] or ["未配置"]:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("### 4.4 适用场景")
    lines.append("")
    for item in suitable_for or ["未配置"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### 4.5 不适用场景")
    lines.append("")
    for item in not_suitable_for or ["未配置"]:
        lines.append(f"- {item}")
    lines.append("")

    if description_notes:
        lines.append("### 4.2 补充计算字段说明")
        lines.append("")
        for item in description_notes:
            name = str(item.get("name") or "").strip()
            description = str(item.get("description") or "").strip()
            if not name or not description:
                continue
            lines.append(f"- `{name}`：{description}")
        lines.append("")

    lines.append("## 5. 字段明细")
    lines.append("")
    dimension_rows = _dimension_rows(spec, context)
    metric_rows = _metric_rows(spec, context)
    lines.append("| 展示名 | Tableau 字段 | Tableau 类型 | metadata 类型 | 角色 | 业务定义 | 定义来源 | 示例/规则 | 证据 | Review |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    if yaml_fields:
        tableau_type_by_name = {
            str(item.get("name") or ""): str(item.get("data_type") or "")
            for item in [*dims, *meas]
            if item.get("name")
        }
        for field in yaml_fields:
            source_field = _field_source_name(field)
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(field.get("display_name") or field.get("name")),
                        _code(source_field),
                        _code(tableau_type_by_name.get(source_field)),
                        _code(field.get("type")),
                        _code(field.get("role")),
                        _cell(_definition_text(field)),
                        _code(_definition_source(field)),
                        _cell(_format_sample_cell(_safe_list_str(_safe_mapping(field).get("sample_values")))),
                        _evidence_cell(field),
                        _cell(_review_text(field)),
                    ]
                )
                + " |"
            )
    else:
        for name, row in dimension_rows.items():
            explanation = _dimension_explanation(name, row) or "待补充维度定义"
            sample_values = _format_sample_cell(_safe_list_str(row.get("sample_values")))
            lines.append(
                f"| {_cell(name)} | `{name}` | `{row.get('data_type', '')}` | `未配置` | `dimension` | "
                f"{_cell(explanation)} | `字段名推断` | {_cell(sample_values)} | 未配置 | 待确认 |"
            )
    lines.append("")

    lines.append("## 6. 指标明细")
    lines.append("")
    if yaml_metrics:
        lines.append("| 指标 | Tableau 字段 | 表达式 | 聚合方式 | 单位 | 业务定义 | 定义来源 | 证据 | Review |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for metric in yaml_metrics:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(metric.get("display_name") or metric.get("name")),
                        _code(_metric_source_name(metric)),
                        _code(_metric_expression(metric)),
                        _code(metric.get("aggregation")),
                        _code(metric.get("unit")),
                        _cell(_definition_text(metric)),
                        _code(_definition_source(metric)),
                        _evidence_cell(metric),
                        _cell(_review_text(metric)),
                    ]
                )
                + " |"
            )
    elif metric_rows:
        lines.append("| 指标 | Tableau 字段 | 标准指标ID | 标准名称 | 单位 | 业务定义 | 定义来源 | 证据 | Review |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for row in metric_rows.values():
            lines.append(
                f"| {_cell(row.get('name'))} | {_code(row.get('name'))} | {_code(row.get('metric_id'))} | "
                f"{_cell(row.get('name_cn'))} | {_code(row.get('unit'))} | "
                f"{_cell(row.get('definition') or '待补充指标定义')} | `标准映射` | 未配置 | 待确认 |"
            )
    else:
        lines.append("- 无指标。")
    lines.append("")

    lines.append("## 7. 筛选器明细")
    lines.append("")
    lines.append("Tableau 离散筛选通过 `--vf` 传入；本节只列出当前视图暴露的筛选字段。")
    if not _has_sample_values(filters):
        lines.append("")
        lines.append("- 本次未采集到筛选器样例值，不能把本节当作完整枚举清单。")
    lines.append("")
    lines.append("| 字段 | 当前类型 | 传参方式 | 示例值/规则 | 说明 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in filters:
        field = str(item.get("tableau_field") or item.get("key") or "")
        usage = _usage_example_for_filter(item)
        values = _safe_list_str(item.get("sample_values"))
        sample_text = _format_sample_cell(values) if values else "未采集"
        suggestion = "适合精确筛选" if usage and usage != "不建议直接使用" else "需结合 Tableau 页面或导出验证确认"
        lines.append(
            f"| `{field}` | `{item.get('kind', 'unknown') or 'unknown'}` | `--vf` | {_cell(sample_text)} | {suggestion} |"
        )
    lines.append("")

    lines.append("## 8. Tableau 使用方式")
    lines.append("")
    lines.append("Tableau 参数必须使用 `--vp`，不要把日期参数误传成 `--vf`。")
    lines.append("")
    if params:
        lines.append("| 参数 | 推荐格式 | 示例 | 用途 |")
        lines.append("| --- | --- | --- | --- |")
        for item in params:
            field = str(item.get("tableau_field") or item.get("key") or "")
            if "开始" in field:
                example_value = start_date
                purpose = "控制时间窗开始日期"
            elif "结束" in field:
                example_value = end_date
                purpose = "控制时间窗结束日期"
            else:
                example_value = start_date
                purpose = "控制查询参数"
            lines.append(f'| `{field}` | `YYYY-MM-DD` | `--vp "{field}={example_value}"` | {purpose} |')
        lines.append("")
    else:
        lines.append("- 当前视图未发现 Tableau 参数。")
        lines.append("")

    lines.append("推荐命令：")
    lines.append("")
    lines.append("```bash")
    lines.append(
        f'python3 {WORKSPACE_DIR / ".agents" / "skills" / "tableau" / "scripts" / "export_source.py"} \\'
    )
    lines.append(f'  --source-id {entry.get("source_id", "")} \\')
    for item in params:
        field = str(item.get("tableau_field") or item.get("key") or "")
        value = start_date if "开始" in field else end_date if "结束" in field else start_date
        lines.append(f'  --vp "{field}={value}" \\')
    if filters:
        filter_item = filters[0]
        filter_field = str(filter_item.get("tableau_field") or filter_item.get("key") or "")
        filter_values = _safe_list_str(filter_item.get("sample_values"))
        if filter_field and filter_values:
            lines.append(f'  --vf "{filter_field}={filter_values[0]}"')
        else:
            lines[-1] = lines[-1].rstrip(" \\")
    else:
        lines[-1] = lines[-1].rstrip(" \\")
    lines.append("```")
    lines.append("")

    lines.append("## 9. 映射与 Review 问题")
    lines.append("")
    lines.append("### 9.1 已注册映射")
    lines.append("")
    if mapping_rows:
        lines.append("| 源字段 | 类型 | 标准 ID | 字段 ID/覆盖 | 说明 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in mapping_rows:
            lines.append(
                f"| {_code(row.get('view_field'))} | {_code(row.get('type'))} | "
                f"{_code(row.get('standard_id'))} | {_code(row.get('field_id_or_override'))} | {_cell(_mapping_note(row))} |"
            )
    else:
        lines.append("| 源字段 | 标准指标ID | 标准名称 | 单位 | 说明 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in metric_rows.values():
            lines.append(
                f"| `{row.get('name', '')}` | `{row.get('metric_id', '')}` | {row.get('name_cn', '')} | `{row.get('unit', '')}` | {row.get('definition', '') or '待补充'} |"
            )
    lines.append("")
    lines.append("### 9.2 待确认问题")
    lines.append("")
    if review_fields or review_metrics or pending_questions:
        lines.append(f"- 待确认字段：`{len(review_fields)}` 个")
        if review_fields:
            lines.append("  - " + "、".join(f"`{field.get('display_name') or field.get('name')}`" for field in review_fields))
        lines.append(f"- 待确认指标：`{len(review_metrics)}` 个")
        if review_metrics:
            lines.append("  - " + "、".join(f"`{metric.get('display_name') or metric.get('name')}`" for metric in review_metrics))
        for question in pending_questions:
            lines.append(f"- {question}")
    else:
        lines.append("- 无待确认字段或指标。")
    unresolved_source = unresolved_dimensions or [name for name, row in dimension_rows.items() if row.get("status") != "mapped"]
    if unresolved_source:
        lines.append("- 尚未标准化维度：" + "、".join(f"`{name}`" for name in unresolved_source))
    lines.append("")

    lines.extend(_export_section(entry=entry, export_summary=export_summary, manifest=manifest))

    lines.append("## 11. 本条数据源的结论")
    lines.append("")
    lines.append(f"- 这条 Tableau 数据源已登记为 `{entry.get('source_id', '')}`")
    if dataset:
        lines.append("- 当前报告基于 metadata YAML、mapping YAML、runtime spec 和 Tableau discovery/sync 素材共同生成")
    else:
        lines.append("- 当前报告仅基于 runtime registry/spec 生成；建议补齐 metadata YAML 后再作为业务口径材料")
    lines.append("- Tableau 视图适合作为运行入口和参数/筛选器说明，不直接替代底层业务口径来源")
    if review_fields or review_metrics:
        lines.append("- 存在待确认字段或指标；带 `待确认` 标记的内容不能作为最终确定口径")
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
