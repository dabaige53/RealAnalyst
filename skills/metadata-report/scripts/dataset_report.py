#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from skills.metadata.lib.metadata_facts import MISSING, UNREGISTERED, read_all_dataset_facts, read_dataset_facts


NUMERIC_TYPES = {"number", "integer", "float", "double", "decimal"}
DATE_TYPES = {"date", "datetime", "time", "timestamp"}


def default_output_dir(workspace: Path) -> Path:
    return workspace / "metadata" / "reports"


def report_path(output_dir: Path, dataset_id: str) -> Path:
    return output_dir / f"{dataset_id}_metadata_report.md"


def read_facts(workspace: Path, *, dataset_id: str | None, all_datasets: bool) -> list[dict[str, Any]]:
    if all_datasets:
        return read_all_dataset_facts(workspace)
    if not dataset_id:
        raise ValueError("Specify --dataset-id or --all")
    return [read_dataset_facts(workspace, dataset_id)]


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _list_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in _list(value) if isinstance(item, dict)]


def _map(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _cell(value: Any) -> str:
    text = _text(value)
    if not text:
        text = MISSING
    return text.replace("|", "\\|").replace("\n", " ")


def _join(values: list[Any]) -> str:
    clean = [_text(value) for value in values if _text(value)]
    return "、".join(clean) if clean else MISSING


def _source_field(item: dict[str, Any]) -> str:
    for key in ("source_field", "physical_name", "name"):
        value = _text(item.get(key))
        if value:
            return value
    return ""


def _definition(item: dict[str, Any]) -> dict[str, Any]:
    return _map(item.get("business_definition"))


def _is_pending(item: dict[str, Any]) -> bool:
    definition = _definition(item)
    return (
        definition.get("needs_review") is True
        or item.get("review_required") is True
        or definition.get("source_type") == "pending"
    )


def _definition_text(item: dict[str, Any]) -> str:
    if _is_pending(item):
        return "业务定义待确认"
    return _text(_definition(item).get("text")) or MISSING


def _definition_source(item: dict[str, Any]) -> str:
    if _is_pending(item):
        return "pending"
    definition = _definition(item)
    return _text(definition.get("ref") or definition.get("source_type")) or MISSING


def _definition_status(item: dict[str, Any]) -> str:
    definition = _definition(item)
    if _is_pending(item):
        return "待补齐"
    if _text(definition.get("text")):
        return "已维护"
    return MISSING


def _definition_path(dataset_id: str, section: str, item: dict[str, Any]) -> str:
    name = _text(item.get("name") or item.get("display_name"))
    return f"metadata/datasets/{dataset_id}.yaml::{section}[name={name}].business_definition" if name else MISSING


def _metric_expression(metric: dict[str, Any]) -> str:
    return _text(metric.get("expression") or metric.get("aggregation") or metric.get("source_field") or metric.get("name"))


def _range_text(start: Any, end: Any) -> str:
    if start is None and end is None:
        return MISSING
    return f"{_text(start) or MISSING} 至 {_text(end) or MISSING}"


def _registered_value(spec_item: dict[str, Any], field: dict[str, Any]) -> str:
    field_type = _text(field.get("type") or field.get("data_type") or spec_item.get("data_type") or spec_item.get("type")).lower()
    validation = _map(spec_item.get("validation"))
    range_payload = spec_item.get("range") if isinstance(spec_item.get("range"), dict) else {}

    if field_type in NUMERIC_TYPES:
        minimum = validation.get("min") or validation.get("minimum") or range_payload.get("min") or range_payload.get("minimum")
        maximum = validation.get("max") or validation.get("maximum") or range_payload.get("max") or range_payload.get("maximum")
        if minimum is not None or maximum is not None:
            return _range_text(minimum, maximum)

    if field_type in DATE_TYPES:
        earliest = validation.get("earliest") or validation.get("min_date") or range_payload.get("earliest") or range_payload.get("min_date")
        latest = validation.get("latest") or validation.get("max_date") or range_payload.get("latest") or range_payload.get("max_date")
        if earliest is not None or latest is not None:
            return _range_text(earliest, latest)

    values = (
        spec_item.get("allowed_values")
        or spec_item.get("values")
        or validation.get("allowed_values")
        or validation.get("values")
    )
    if isinstance(values, list) and values:
        text = "、".join(_text(value) for value in values if _text(value))
        return text or MISSING
    return MISSING


def _spec_lookup(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for key in ("filters", "dimensions", "parameters"):
        for item in _list_dicts(spec.get(key)):
            name = _text(item.get("key") or item.get("name") or item.get("tableau_field"))
            if name:
                lookup.setdefault(name, item)
    return lookup


def _filter_rows(dataset: dict[str, Any], spec: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    lookup = _spec_lookup(spec)
    for field in _list_dicts(dataset.get("fields")):
        role = _text(field.get("role")).lower()
        if role not in {"dimension", "time_dimension", "identifier", "category"}:
            continue
        source = _source_field(field)
        spec_item = lookup.get(source) or lookup.get(_text(field.get("name"))) or {}
        field_type = _text(field.get("type")).lower()
        value_kind = "日期范围" if field_type in DATE_TYPES else "数值范围" if field_type in NUMERIC_TYPES else "取值列表"
        rows.append(
            {
                "名称": _text(field.get("display_name") or field.get("name")),
                "类型": "时间字段" if role == "time_dimension" else "筛选字段",
                "取值类型": value_kind,
                "已维护取值或范围": _registered_value(spec_item, field),
                "使用方式": _text(spec_item.get("apply_via")) or ("--vf" if _text(dataset.get("source", {}).get("connector")) == "tableau" else "sql_where"),
                "来源": "runtime/registry" if spec_item else MISSING,
            }
        )
    for parameter in _list_dicts(spec.get("parameters")):
        name = _text(parameter.get("tableau_field") or parameter.get("key") or parameter.get("name"))
        if name:
            rows.append(
                {
                    "名称": name,
                    "类型": "参数",
                    "取值类型": "参数取值",
                    "已维护取值或范围": _registered_value(parameter, {}),
                    "使用方式": "--vp",
                    "来源": "runtime/registry",
                }
            )
    return rows


def _mapping_rows(facts: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for mapping in facts.get("mappings") or []:
        source_path = _text(mapping.get("_metadata_path")) or "metadata/mappings"
        for row in _list_dicts(mapping.get("mappings")):
            rows.append(
                {
                    "来源文件": source_path,
                    "源字段": _text(row.get("view_field")),
                    "类型": _text(row.get("type")),
                    "标准语义": _text(row.get("standard_id")),
                    "本地字段": _text(row.get("field_id_or_override")),
                    "说明": _text(row.get("definition_override") or row.get("notes")),
                }
            )
    return rows


def _gaps(facts: dict[str, Any], filter_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    dataset_id = facts["dataset_id"]
    dataset = facts["dataset"]
    rows: list[dict[str, str]] = []
    for section in ("fields", "metrics"):
        for item in _list_dicts(dataset.get(section)):
            if _definition_status(item) != "已维护":
                rows.append(
                    {
                        "对象": _text(item.get("display_name") or item.get("name")),
                        "类型": "字段" if section == "fields" else "指标",
                        "缺口": "business_definition 未维护" if not _is_pending(item) else "business_definition 待补齐",
                        "位置": _definition_path(dataset_id, section, item),
                    }
                )
    for row in filter_rows:
        if row["已维护取值或范围"] == MISSING:
            rows.append(
                {
                    "对象": row["名称"],
                    "类型": row["类型"],
                    "缺口": "取值或范围未维护",
                    "位置": "runtime/registry",
                }
            )
    status = facts.get("status") or {}
    if not status.get("runtime_registry"):
        rows.append({"对象": dataset_id, "类型": "注册状态", "缺口": UNREGISTERED, "位置": _text(status.get("registry_db"))})
    return rows


def _table(lines: list[str], headers: list[str], rows: list[dict[str, Any]]) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(_cell(row.get(header)) for header in headers) + " |")
    lines.append("")


def render_dataset_report(facts: dict[str, Any], *, output_dir: Path) -> str:
    dataset = facts["dataset"]
    dataset_id = facts["dataset_id"]
    source = _map(dataset.get("source"))
    business = _map(dataset.get("business"))
    registry = _map(facts.get("registry"))
    spec = _map(registry.get("spec"))
    status = _map(facts.get("status"))
    fields = _list_dicts(dataset.get("fields"))
    metrics = _list_dicts(dataset.get("metrics"))
    filter_rows = _filter_rows(dataset, spec)
    mapping_rows = _mapping_rows(facts)
    gaps = _gaps(facts, filter_rows)
    generated_at = _text(facts.get("generated_at")) or datetime.now().astimezone().isoformat(timespec="seconds")

    lines = [f"# {_cell(dataset.get('display_name') or dataset_id)} 元数据报告", ""]
    lines.extend(["## 1. 元数据事实摘要", ""])
    _table(
        lines,
        ["项目", "内容", "来源"],
        [
            {"项目": "数据集", "内容": dataset.get("display_name") or dataset_id, "来源": "metadata/datasets"},
            {"项目": "系统标识", "内容": dataset_id, "来源": "metadata/datasets"},
            {"项目": "连接器", "内容": source.get("connector"), "来源": "metadata/datasets"},
            {"项目": "字段数", "内容": str(len(fields)), "来源": "metadata/datasets"},
            {"项目": "指标数", "内容": str(len(metrics)), "来源": "metadata/datasets"},
            {"项目": "注册状态", "内容": registry.get("status") or UNREGISTERED, "来源": "runtime/registry"},
        ],
    )

    lines.extend(["## 2. 数据集信息", ""])
    _table(
        lines,
        ["项目", "内容", "来源"],
        [
            {"项目": "展示名称", "内容": dataset.get("display_name"), "来源": "metadata/datasets"},
            {"项目": "业务说明", "内容": dataset.get("description") or business.get("description"), "来源": "metadata/datasets"},
            {"项目": "业务域", "内容": business.get("domain"), "来源": "metadata/datasets"},
            {"项目": "分析粒度", "内容": _join(_list(business.get("grain"))), "来源": "metadata/datasets"},
            {"项目": "主键", "内容": _join(_list(business.get("primary_key"))), "来源": "metadata/datasets"},
            {"项目": "时间字段", "内容": _join(_list(business.get("time_fields"))), "来源": "metadata/datasets"},
            {"项目": "适用场景", "内容": _join(_list(business.get("suitable_for"))), "来源": "metadata/datasets"},
            {"项目": "不适用场景", "内容": _join(_list(business.get("not_suitable_for"))), "来源": "metadata/datasets"},
        ],
    )

    if fields:
        lines.extend(["## 3. 字段信息", ""])
        _table(
            lines,
            ["名称", "系统标识", "物理字段", "角色", "类型", "业务定义", "定义来源", "状态", "来源"],
            [
                {
                    "名称": field.get("display_name") or field.get("name"),
                    "系统标识": field.get("name"),
                    "物理字段": _source_field(field),
                    "角色": field.get("role"),
                    "类型": field.get("type"),
                    "业务定义": _definition_text(field),
                    "定义来源": _definition_source(field),
                    "状态": _definition_status(field),
                    "来源": _definition_path(dataset_id, "fields", field),
                }
                for field in fields
            ],
        )

    if metrics:
        lines.extend(["## 4. 指标信息", ""])
        _table(
            lines,
            ["指标", "系统标识", "表达式", "聚合方式", "单位", "适用粒度", "业务定义", "定义来源", "状态", "来源"],
            [
                {
                    "指标": metric.get("display_name") or metric.get("name"),
                    "系统标识": metric.get("name"),
                    "表达式": _metric_expression(metric),
                    "聚合方式": metric.get("aggregation"),
                    "单位": metric.get("unit"),
                    "适用粒度": _join(_list(metric.get("valid_grains"))),
                    "业务定义": _definition_text(metric),
                    "定义来源": _definition_source(metric),
                    "状态": _definition_status(metric),
                    "来源": _definition_path(dataset_id, "metrics", metric),
                }
                for metric in metrics
            ],
        )

    if filter_rows:
        lines.extend(["## 5. 筛选、参数与取值信息", ""])
        _table(lines, ["名称", "类型", "取值类型", "已维护取值或范围", "使用方式", "来源"], filter_rows)

    if mapping_rows:
        lines.extend(["## 6. 映射与来源追溯", ""])
        _table(lines, ["来源文件", "源字段", "类型", "标准语义", "本地字段", "说明"], mapping_rows)

    if gaps:
        lines.extend(["## 7. 未维护项", ""])
        _table(lines, ["对象", "类型", "缺口", "位置"], gaps)

    lines.extend(["## 8. 运行与注册状态", ""])
    _table(
        lines,
        ["项目", "状态", "来源"],
        [
            {"项目": "metadata YAML", "状态": "已维护" if status.get("metadata_yaml") else MISSING, "来源": status.get("metadata_path")},
            {"项目": "metadata index", "状态": "已维护" if status.get("metadata_index") else MISSING, "来源": "metadata/index"},
            {"项目": "runtime registry", "状态": "已注册" if status.get("runtime_registry") else UNREGISTERED, "来源": status.get("registry_db")},
            {"项目": "runtime spec", "状态": "已维护" if status.get("runtime_spec") else MISSING, "来源": status.get("registry_db")},
        ],
    )

    lines.extend(["## 9. 报告生成信息", ""])
    _table(
        lines,
        ["项目", "内容"],
        [
            {"项目": "生成时间", "内容": generated_at},
            {"项目": "生成入口", "内容": "skills/metadata-report/scripts/generate_report.py"},
            {"项目": "读取入口", "内容": "skills/metadata/lib/metadata_facts.py"},
            {"项目": "默认输出目录", "内容": str(output_dir)},
        ],
    )
    return "\n".join(lines).rstrip() + "\n"


def write_dataset_report(facts: dict[str, Any], *, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = report_path(output_dir, facts["dataset_id"])
    path.write_text(render_dataset_report(facts, output_dir=output_dir), encoding="utf-8")
    return path
