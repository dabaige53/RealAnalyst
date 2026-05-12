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

from runtime.tableau.sqlite_store import list_entries, load_spec_by_entry_key  # noqa: E402
from skills.metadata.lib.metadata_io import (  # noqa: E402
    MetadataError,
    load_dataset_file,
    load_mapping_file,
    normalize_dataset,
    resolve_dataset_path,
)
from skills.metadata.lib.value_patterns import infer_value_pattern  # noqa: E402
from report_context import build_report_context, render_markdown  # noqa: E402


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
    return source


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
            "source": "Tableau spec",
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
    return str(row.get("definition") or row.get("description") or "")


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


def _source_summary_cell(item: dict[str, Any]) -> str:
    source_text = _review_source_text(item)
    if source_text == "来源未配置":
        return _definition_source(item)
    return source_text


def _review_location(section: str, item: dict[str, Any], dataset_id: str) -> str:
    name = str(item.get("name") or item.get("display_name") or "").strip()
    selector = f"{section}[name={name}].business_definition.text" if name else f"{section}.business_definition.text"
    return f"metadata/datasets/{dataset_id}.yaml::{selector}"


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
    dataset = _load_yaml_dataset_if_exists(str(entry.get("source_id") or ""))
    mapping = _load_mapping_for_dataset(dataset)
    report_context = build_report_context(
        connector="tableau",
        dataset=dataset,
        mapping=mapping,
        entry=entry,
        spec=spec,
        source_context=context,
        sample_values=None,
        duckdb_meta=None,
        export_summary=export_summary,
        manifest=manifest,
        step_results=step_results,
        generated_at=generated_at,
        report_dir=report_dir,
    )
    return render_markdown(report_context)


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
