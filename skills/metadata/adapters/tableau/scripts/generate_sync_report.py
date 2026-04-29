#!/usr/bin/env python3
"""Generate detailed Markdown sync reports for Tableau registry entries."""

from __future__ import annotations

import argparse
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


def default_report_dir() -> Path:
    return WORKSPACE_DIR / "metadata" / "sync" / "tableau" / "reports"


def build_report_filename(source_id: str, *, generated_at: datetime) -> str:
    timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{source_id}_sync_report.md"


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
    return [f"- `{value}`" for value in values]


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
    lines.append("## 9. 实际导出验证结果")
    lines.append("")

    if not export_summary:
        lines.append("- 当前未执行正式导出验证。")
        lines.append("- 本次报告仅覆盖 registry/spec/source_context 同步结果。")
        lines.append("- 若需要补完整验证段，后续可在导出后把 `export_summary.json` 与 `manifest` 一并注入本报告生成链路。")
        lines.append("")
        return lines

    page_url = str((((export_summary.get("views") or [None])[0]) or {}).get("tableau", {}).get("page_url") or _page_url(entry))
    lines.append("### 9.1 导出执行结果")
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
        lines.append("### 9.2 实际导出物理列")
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
            lines.append("### 9.3 需要特别说明的结构差异")
            lines.append("")
            lines.append("这条数据源存在“逻辑字段 vs 物理列”差异：")
            lines.append("")
            lines.append(f"- registry/spec 中逻辑可用字段共 `{logical_count}` 个")
            lines.append(f"- 实际导出的 CSV 物理列共 `{physical_count}` 个")
            lines.append("- 这通常意味着部分业务指标通过 `度量名称` / `度量值` 以长表方式表达，而不是宽表独立列")
            lines.append("- 后续分析前应先核对这份同步报告或 `export_summary.json`，确认当前导出是宽表还是长表")
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
    description_notes = _safe_list_dicts(spec.get("description_notes"))
    unresolved_dimensions = _safe_list_str(context.get("unresolved_dimensions"))
    start_date, end_date = _default_date_examples(spec, generated_at)

    lines: list[str] = []
    lines.append("# Tableau Sync Report")
    lines.append("")
    lines.append("## 1. 同步任务概览")
    lines.append("")
    lines.append("- 报告类型：Tableau 数据源同步明细报告")
    lines.append(f"- 报告生成时间：{generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 同步对象：`{entry.get('source_id', '')}`")
    lines.append(f"- 显示名称：`{entry.get('display_name', '')}`")
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
    tableau = entry.get("tableau") if isinstance(entry.get("tableau"), dict) else {}
    lines.append(f"| `view_luid` | `{tableau.get('view_luid', '')}` |")
    lines.append(f"| `view_name` | `{tableau.get('view_name', '')}` |")
    lines.append(f"| `content_url` | `{tableau.get('content_url', '')}` |")
    if page_url:
        lines.append(f"| `page_url` | `{page_url}` |")
    lines.append(f"| `workbook_id` | `{tableau.get('workbook_id', '')}` |")
    lines.append(f"| `workbook_name` | `{tableau.get('workbook_name', '') or '空字符串，当前 Tableau API 未返回名称'}` |")
    lines.append(f"| `description` | `{entry.get('description', '') or '当前 registry 内为空，尚未固化业务描述'}` |")
    lines.append("")

    lines.append("## 3. 本次写入摘要")
    lines.append("")
    lines.append("### 3.1 注册层")
    lines.append("")
    lines.append(f"- 当前 registry 条目状态：`{entry.get('status', '')}`")
    lines.append(f"- 当前 spec 更新时间：`{spec.get('updated', '')}`")
    lines.append("- 仍为空的注册信息：")
    empty_fields = []
    for name, value in [
        ("description", entry.get("description")),
        ("workbook_name", tableau.get("workbook_name")),
        ("semantics.grain", semantics.get("grain")),
        ("semantics.suitable_for", semantics.get("suitable_for")),
        ("semantics.not_suitable_for", semantics.get("not_suitable_for")),
    ]:
        if value in (None, "", [], {}):
            empty_fields.append(name)
    if empty_fields:
        lines.extend([f"- `{field}`" for field in empty_fields])
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("### 3.2 字段层")
    lines.append("")
    lines.append(f"- 当前维度数：`{len(dims)}`")
    lines.append(f"- 当前指标数：`{len(meas)}`")
    lines.append(f"- 合并后逻辑字段总数：`{len(dims) + len(meas)}`")
    lines.append(f"- 是否采样维度样例值：{'是' if with_samples else '否'}")
    lines.append("")

    lines.append("### 3.3 筛选器与参数层")
    lines.append("")
    lines.append(f"- 当前筛选器数：`{len(filters)}`")
    lines.append(f"- 当前参数数：`{len(params)}`")
    unresolved_validation = [
        (item.get("tableau_field") or item.get("key") or "")
        for item in filters + params
        if not (item.get("validation") if isinstance(item.get("validation"), dict) else {})
    ]
    lines.append("- 当前仍未固化 validation 的对象：")
    if unresolved_validation:
        lines.extend([f"- `{name}`" for name in unresolved_validation if name])
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("### 3.4 语义层")
    lines.append("")
    primary_dimensions_count = len(_safe_list_str(semantics.get("primary_dimensions")))
    available_metrics_count = len(_safe_list_str(semantics.get("available_metrics")))
    lines.append(f"- 当前 `primary_dimensions`：`{primary_dimensions_count}`")
    lines.append(f"- 当前 `available_metrics`：`{available_metrics_count}`")
    metric_summary = context.get("mapping_summary", {}).get("metrics", {}) if isinstance(context.get("mapping_summary"), dict) else {}
    dim_summary = context.get("mapping_summary", {}).get("dimensions", {}) if isinstance(context.get("mapping_summary"), dict) else {}
    lines.append(
        f"- 指标标准映射：`{metric_summary.get('mapped', 0)}/{metric_summary.get('total', len(meas))}` 已映射"
    )
    lines.append(
        f"- 维度标准映射：`{dim_summary.get('mapped', 0)}/{dim_summary.get('total', len(dims))}` 已映射"
    )
    lines.append("- 未解析维度：")
    if unresolved_dimensions:
        lines.extend([f"- `{name}`" for name in unresolved_dimensions])
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("## 4. 建议补充的业务描述")
    lines.append("")
    lines.append("以下内容是为了便于后续使用而生成的人类可读描述，默认不直接回写 registry：")
    lines.append("")
    lines.append(f"> {_description_suggestion(entry, spec, context)}")
    lines.append("")

    if description_notes:
        lines.append("### 4.1 补充计算字段说明")
        lines.append("")
        for item in description_notes:
            name = str(item.get("name") or "").strip()
            description = str(item.get("description") or "").strip()
            if not name or not description:
                continue
            lines.append(f"- `{name}`：{description}")
        lines.append("")

    lines.append("## 5. 逻辑字段明细")
    lines.append("")
    lines.append("| 逻辑字段 | 角色 | 数据类型 | 映射状态 | 标准映射/解释 | 描述来源 | 样例值/备注 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    dimension_rows = _dimension_rows(spec, context)
    for name, row in dimension_rows.items():
        explanation = _dimension_explanation(name, row)
        sample_values = "、".join(_safe_list_str(row.get("sample_values"))[:5])
        lines.append(
            f"| `{name}` | 维度 | `{row.get('data_type', '')}` | `{row.get('status', '')}` | "
            f"{explanation or '待补充维度定义'} | 字段名推断 | {sample_values or '无'} |"
        )
    metric_rows = _metric_rows(spec, context)
    for name, row in metric_rows.items():
        explanation = row.get("definition") or "待补充指标定义"
        label = f"标准指标 `{row.get('metric_id', '')}` / {row.get('name_cn', '')} / `{row.get('unit', '')}`".strip()
        lines.append(
            f"| `{name}` | 指标 | `{row.get('data_type', '')}` | `{row.get('status', '')}` | "
            f"{label} | 标准映射 | {explanation} |"
        )
    lines.append("")

    lines.append("## 6. 筛选器明细")
    lines.append("")
    lines.append("### 6.1 筛选器使用总则")
    lines.append("")
    lines.append("- 本条数据源的筛选器使用 `--vf`")
    lines.append("- 本条数据源的参数使用 `--vp`")
    lines.append("- 样例值来自同步时采样，不代表完整可选集")
    lines.append("- 当前筛选器若未固化 `validation`，使用时应优先参考样例值和实际验证")
    lines.append("")
    lines.append("### 6.2 筛选器清单")
    lines.append("")
    lines.append("| 筛选器 key | Tableau 字段 | 当前类型 | 推荐传参方式 | 示例命令片段 | 使用建议 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for item in filters:
        field = str(item.get("tableau_field") or item.get("key") or "")
        usage = _usage_example_for_filter(item)
        suggestion = "适合精确筛选" if usage and usage != "不建议直接使用" else "更像内部辅助字段"
        lines.append(
            f"| `{field}` | `{field}` | `{item.get('kind', 'unknown') or 'unknown'}` | `--vf` | {usage} | {suggestion} |"
        )
    lines.append("")
    lines.append("### 6.3 筛选器样例值")
    lines.append("")
    for item in filters:
        field = str(item.get("tableau_field") or item.get("key") or "")
        lines.append(f"#### `{field}`")
        lines.append("")
        lines.append("当前采样到的值：")
        lines.append("")
        lines.extend(_render_filter_values(_safe_list_str(item.get("sample_values"))))
        lines.append("")

    lines.append("## 7. 参数明细")
    lines.append("")
    lines.append("### 7.1 参数使用总则")
    lines.append("")
    lines.append("- 参数必须使用 `--vp`")
    lines.append("- 不要把日期参数误传成 `--vf`")
    lines.append("- 若当前未固化 validation，默认推荐使用 `YYYY-MM-DD`")
    lines.append("")
    lines.append("### 7.2 参数清单")
    lines.append("")
    lines.append("| 参数 key | Tableau 字段 | 推荐格式 | 传参方式 | 示例 | 用途说明 | 当前校验状态 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
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
        validation = "已固化 validation" if item.get("validation") else "未固化 validation"
        lines.append(
            f'| `{field}` | `{field}` | `YYYY-MM-DD` | `--vp` | `--vp "{field}={example_value}"` | {purpose} | {validation} |'
        )
    lines.append("")
    lines.append("### 7.3 推荐使用方式")
    lines.append("")
    lines.append("推荐优先通过参数控制时间窗，再按离散筛选器细化查询。例如：")
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

    lines.append("## 8. 指标与维度映射结果")
    lines.append("")
    lines.append("### 8.1 已映射指标")
    lines.append("")
    lines.append("| 源字段 | 标准指标ID | 标准名称 | 单位 | 说明 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in metric_rows.values():
        lines.append(
            f"| `{row.get('name', '')}` | `{row.get('metric_id', '')}` | {row.get('name_cn', '')} | `{row.get('unit', '')}` | {row.get('definition', '') or '待补充'} |"
        )
    lines.append("")
    lines.append("### 8.2 尚未标准化的维度")
    lines.append("")
    lines.append("| 源字段 | 当前状态 | 建议解释 | 备注 |")
    lines.append("| --- | --- | --- | --- |")
    for name, row in dimension_rows.items():
        lines.append(
            f"| `{name}` | `{row.get('status', '')}` | {_dimension_explanation(name, row) or '待补充维度解释'} | 建议后续补维度映射或别名 |"
        )
    lines.append("")

    lines.extend(_export_section(entry=entry, export_summary=export_summary, manifest=manifest))

    lines.append("## 10. 本条数据源的结论")
    lines.append("")
    lines.append(f"- 这条 Tableau 数据源已登记为 `{entry.get('source_id', '')}`")
    lines.append("- 当前 metadata / spec / semantics 已完成同步")
    lines.append("- 指标语义映射相对完整，维度标准化仍需后续补充")
    if params:
        param_names = "、".join(str(item.get("tableau_field") or item.get("key") or "") for item in params)
        lines.append(f"- 时间控制建议优先通过 `{param_names}` 等参数完成")
    if filters:
        lines.append("- 离散筛选建议通过 `--vf` 使用本报告中列出的字段和样例值")
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
    parser = argparse.ArgumentParser(description="Generate detailed Tableau sync Markdown reports")
    parser.add_argument("--key", help="Generate report for a specific entry key")
    parser.add_argument("--all", action="store_true", help="Generate reports for all active entries")
    parser.add_argument("--report-dir", help="Output directory for Markdown reports")
    parser.add_argument("--with-samples", action="store_true", help="Indicate this sync included sample values")
    parser.add_argument("--sync-mode", choices=["live", "dry-run"], default="live")
    parser.add_argument("--fields-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--filters-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--registry-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--export-summary", help="Optional export_summary.json path to enrich validation section")
    parser.add_argument("--manifest", help="Optional manifest JSON path to enrich validation section")
    args = parser.parse_args()

    if not args.key and not args.all:
        print("[Error] Specify --key KEY or --all")
        raise SystemExit(2)

    targets = _load_targets(key=args.key, all_entries=args.all)
    if not targets:
        print("[WARN] No entries matched")
        return

    export_summary = _parse_export_payload(args.export_summary)
    manifest = _parse_export_payload(args.manifest)
    report_dir = Path(args.report_dir).expanduser().resolve() if args.report_dir else default_report_dir()
    generated_at = datetime.now()
    step_results = {
        "fields": args.fields_step_status,
        "filters": args.filters_step_status,
        "registry": args.registry_step_status,
    }

    for entry in targets:
        key = str(entry.get("key") or "")
        spec = load_spec_by_entry_key(key) or {}
        context = build_source_context(entry)
        report_path = write_report(
            entry=entry,
            spec=spec,
            context=context,
            report_dir=report_dir,
            generated_at=generated_at,
            with_samples=args.with_samples,
            sync_mode=args.sync_mode,
            step_results=step_results,
            export_summary=export_summary,
            manifest=manifest,
        )
        print(f"[OK] report -> {report_path}")


if __name__ == "__main__":
    main()
