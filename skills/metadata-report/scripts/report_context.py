#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from skills.metadata.lib.value_patterns import clean_sample_values, infer_value_pattern


PENDING_TEXT = "业务定义待确认"


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _list_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in _list(value) if isinstance(item, dict)]


def _list_str(value: Any) -> list[str]:
    return [str(item).strip() for item in _list(value) if str(item or "").strip()]


def _map(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _connection_ref_text(value: Any) -> str:
    text = _text(value)
    lowered = text.lower()
    if "://" in text or "@" in text or "password" in lowered or "token" in lowered or "\n" in text:
        return "[redacted]"
    return text


def _cell(value: Any) -> str:
    return _text(value).replace("|", "\\|").replace("\n", " ")


def _code(value: Any) -> str:
    text = _text(value).replace("`", "")
    return f"`{text}`" if text else ""


def _path_text(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(path)


def _join(values: list[str], *, limit: int = 4) -> str:
    clean = [value for value in values if value]
    if not clean:
        return ""
    suffix = f" 等 {len(clean)} 项" if len(clean) > limit else ""
    return "、".join(clean[:limit]) + suffix


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
        return PENDING_TEXT
    definition = _definition(item)
    return _text(definition.get("text") or "")


def _definition_status(item: dict[str, Any]) -> str:
    definition = _definition(item)
    confidence = definition.get("confidence")
    suffix = f"（置信度 {confidence}）" if isinstance(confidence, (int, float)) else ""
    if _is_pending(item):
        return f"待补齐{suffix}"
    if _text(definition.get("text")):
        return f"已确认{suffix}"
    return "仅结构可用"


def _definition_location(dataset_id: str, section: str, item: dict[str, Any]) -> str:
    if dataset_id and dataset_id != "unknown" and _text(item.get("name") or item.get("display_name")):
        name = _text(item.get("name") or item.get("display_name"))
        return f"metadata/datasets/{dataset_id}.yaml::{section}[name={name}].business_definition"
    return ""


def _has_confirmed_definition(item: dict[str, Any]) -> bool:
    return bool(_text(_definition(item).get("text"))) and not _is_pending(item)


def _role_label(role: str) -> str:
    return {
        "time_dimension": "时间",
        "dimension": "维度",
        "metric_source": "指标来源",
        "measure_candidate": "指标来源",
        "identifier": "标识",
        "attribute": "属性",
    }.get(role, "属性")


def _field_source(field: dict[str, Any]) -> str:
    for key in ("source_field", "physical_name", "name"):
        value = _text(field.get(key))
        if value:
            return value
    return ""


def _metric_source(metric: dict[str, Any]) -> str:
    source_mapping = _map(metric.get("source_mapping"))
    for key_value in (metric.get("source_field"), source_mapping.get("view_field"), metric.get("expression"), metric.get("name")):
        value = _text(key_value)
        if value:
            return value.replace("`", "")
    return ""


def _metric_lookup(metrics: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for metric in metrics:
        source = _metric_source(metric)
        if source:
            lookup.setdefault(source, metric)
        name = _text(metric.get("name"))
        if name:
            lookup.setdefault(name, metric)
    return lookup


def _sample_text(values: list[Any]) -> str:
    pattern = infer_value_pattern(values)
    if pattern:
        return f"{pattern['example']}（格式：`{pattern['regex']}`）"
    cleaned = clean_sample_values(values)
    return "、".join(cleaned[:5]) if cleaned else ""


def _mapping_note(row: dict[str, Any]) -> str:
    note = _text(row.get("definition_override") or row.get("notes"))
    if any(marker in note for marker in ("待确认", "待补齐", "需确认", "具体业务口径", "指标候选")):
        return PENDING_TEXT
    return note


def _gap_location(dataset_id: str, section: str, item: dict[str, Any]) -> str:
    name = _text(item.get("name") or item.get("display_name"))
    selector = f"{section}[name={name}].business_definition.text" if name else f"{section}.business_definition.text"
    return f"metadata/datasets/{dataset_id}.yaml::{selector}"


@dataclass
class ReportContext:
    dataset_id: str
    display_name: str
    connector: str
    object_kind: str = ""
    description: str = ""
    business_domain: str = ""
    grain: list[str] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    time_fields: list[str] = field(default_factory=list)
    suitable_for: list[str] = field(default_factory=list)
    not_suitable_for: list[str] = field(default_factory=list)
    fields: list[dict[str, str]] = field(default_factory=list)
    metrics: list[dict[str, str]] = field(default_factory=list)
    filters: list[dict[str, str]] = field(default_factory=list)
    parameters: list[dict[str, str]] = field(default_factory=list)
    mappings: list[dict[str, str]] = field(default_factory=list)
    gaps: list[dict[str, str]] = field(default_factory=list)
    boundaries: list[dict[str, str]] = field(default_factory=list)
    technical_rows: list[tuple[str, str]] = field(default_factory=list)
    metadata_sources: list[tuple[str, str, str]] = field(default_factory=list)
    export_rows: list[tuple[str, str]] = field(default_factory=list)
    manifest_columns: list[str] = field(default_factory=list)
    validation_state: str = ""
    generated_at: datetime | None = None
    report_dir: Path | None = None

    def to_chinese_dict(self) -> dict[str, Any]:
        return {
            "数据源ID": self.dataset_id,
            "展示名称": self.display_name,
            "连接器": self.connector,
            "对象类型": self.object_kind,
            "业务说明": self.description,
            "业务域": self.business_domain,
            "分析粒度": self.grain,
            "主键": self.primary_key,
            "时间字段": self.time_fields,
            "可支持场景": self.suitable_for,
            "不适用场景": self.not_suitable_for,
            "字段": self.fields,
            "指标": self.metrics,
            "筛选入口": self.filters,
            "参数": self.parameters,
            "字段映射": self.mappings,
            "待补齐项": self.gaps,
            "边界与风险": self.boundaries,
            "技术信息": dict(self.technical_rows),
            "来源状态": [{"来源": s, "用途": u, "状态": st} for s, u, st in self.metadata_sources],
            "导出验证": dict(self.export_rows),
            "导出物理列": self.manifest_columns,
            "校验状态": self.validation_state,
        }


def write_context_json(context: ReportContext, path: Path) -> None:
    path.write_text(json.dumps(context.to_chinese_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def build_report_context(
    *,
    connector: str,
    dataset: dict[str, Any] | None,
    mapping: dict[str, Any] | None,
    entry: dict[str, Any] | None,
    spec: dict[str, Any] | None,
    source_context: dict[str, Any] | None,
    sample_values: dict[str, list[Any]] | None,
    duckdb_meta: dict[str, Any] | None,
    export_summary: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    step_results: dict[str, str],
    generated_at: datetime,
    report_dir: Path,
) -> ReportContext:
    dataset = dataset or {}
    entry = entry or {}
    spec = spec or {}
    source_context = source_context or {}
    business = _map(dataset.get("business"))
    source = _map(dataset.get("source"))
    maintenance = _map(dataset.get("maintenance"))
    semantics = _map(entry.get("semantics"))
    dataset_id = _text(dataset.get("id") or dataset.get("source_id") or entry.get("source_id") or entry.get("key") or "unknown")
    summary = _map(dataset.get("source_summary"))
    connector_meta = _map(duckdb_meta) or _map(entry.get(connector)) or _map(source.get(connector))
    object_kind = _text(connector_meta.get("object_kind") or entry.get("type") or summary.get("type"))
    context = ReportContext(
        dataset_id=dataset_id,
        display_name=_text(dataset.get("display_name") or entry.get("display_name") or dataset_id),
        connector=connector,
        object_kind=object_kind,
        description=_text(dataset.get("description") or business.get("description") or entry.get("description")),
        business_domain=_text(business.get("domain") or summary.get("category") or entry.get("category")),
        grain=_list_str(business.get("grain")) or _list_str(semantics.get("grain")),
        primary_key=_list_str(business.get("primary_key")),
        time_fields=_list_str(business.get("time_fields")),
        suitable_for=_list_str(business.get("suitable_for")) or _list_str(semantics.get("suitable_for")),
        not_suitable_for=_list_str(business.get("not_suitable_for")) or _list_str(semantics.get("not_suitable_for")),
        validation_state=_text(step_results.get("validate") or step_results.get("registry") or step_results.get("fields")),
        generated_at=generated_at,
        report_dir=report_dir,
    )

    raw_fields = _list_dicts(dataset.get("fields"))
    raw_metrics = _list_dicts(dataset.get("metrics"))
    metric_lookup = _metric_lookup(raw_metrics)
    samples = sample_values or {}

    if not raw_fields and connector == "tableau":
        for item in _list_dicts(spec.get("dimensions")):
            name = _text(item.get("name"))
            if name:
                raw_fields.append(
                    {
                        "name": name,
                        "display_name": name,
                        "source_field": name,
                        "role": "dimension",
                        "type": item.get("data_type"),
                        "business_definition": {},
                    }
                )
    if not raw_metrics and connector == "tableau":
        for item in _list_dicts(spec.get("measures")):
            name = _text(item.get("name"))
            if name:
                raw_metrics.append(
                    {
                        "name": name,
                        "display_name": name,
                        "source_field": name,
                        "expression": name,
                        "aggregation": "Tableau 视图字段",
                        "unit": item.get("unit", ""),
                        "business_definition": {},
                    }
                )

    for field_item in raw_fields:
        source_name = _field_source(field_item)
        role = _text(field_item.get("role"))
        definition_item = metric_lookup.get(source_name) if role in {"metric_source", "measure_candidate"} else None
        definition_item = definition_item or field_item
        status = _definition_status(definition_item)
        sample_text = _sample_text(samples.get(source_name, []))
        context.fields.append(
            {
                "名称": _text(field_item.get("display_name") or field_item.get("name")),
                "元数据字段名": _text(field_item.get("name")),
                "源字段": source_name,
                "类型": _role_label(role),
                "metadata类型": _text(field_item.get("type")),
                "角色": role,
                "业务含义": _definition_text(definition_item),
                "口径状态": status,
                "示例/规则": sample_text,
                "定义位置": _definition_location(dataset_id, "metrics" if definition_item is not field_item else "fields", definition_item),
            }
        )
        if not _has_confirmed_definition(definition_item) and definition_item is field_item:
            context.gaps.append(
                {
                    "优先级": "中",
                    "主题": _text(field_item.get("display_name") or field_item.get("name")),
                    "影响": "影响筛选、分组或字段解释",
                    "当前缺口": "业务定义待补齐",
                    "补齐位置": _gap_location(dataset_id, "fields", field_item),
                    "补齐后用途": "可作为稳定维度或字段口径使用。",
                }
            )

    for metric_item in raw_metrics:
        expression = _text(metric_item.get("expression") or metric_item.get("aggregation") or _metric_source(metric_item)).replace("`", "")
        if not expression:
            continue
        status = _definition_status(metric_item)
        context.metrics.append(
            {
                "指标": _text(metric_item.get("display_name") or metric_item.get("name")),
                "源字段/表达式": _metric_source(metric_item),
                "业务含义": _definition_text(metric_item),
                "计算或聚合方式": expression,
                "单位": _text(metric_item.get("unit")),
                "适用粒度": _join(_list_str(metric_item.get("valid_grains")) or context.grain),
                "口径状态": status,
                "定义位置": _definition_location(dataset_id, "metrics", metric_item),
            }
        )
        if not _has_confirmed_definition(metric_item):
            context.gaps.append(
                {
                    "优先级": "高",
                    "主题": _text(metric_item.get("display_name") or metric_item.get("name")),
                    "影响": "影响指标解释和汇总口径",
                    "当前缺口": "业务定义待补齐",
                    "补齐位置": _gap_location(dataset_id, "metrics", metric_item),
                    "补齐后用途": "可进入正式指标口径。",
                }
            )

    if connector in {"duckdb", "mysql", "clickhouse"}:
        for field_row in context.fields:
            if field_row["类型"] not in {"时间", "维度"}:
                continue
            source_name = field_row["源字段"]
            metadata_name = field_row.get("元数据字段名") or source_name
            context.filters.append(
                {
                    "筛选入口": field_row["名称"],
                    "类型": f"{field_row['类型']}字段",
                    "示例值/规则": field_row["示例/规则"],
                    "使用方式": "sql_where",
                    "使用边界": f"按 {_code(source_name)} 过滤；示例值只用于识别值域。",
                    "来源": f"metadata/datasets/{dataset_id}.yaml::fields[name={metadata_name}].role",
                }
            )
    else:
        start_example = generated_at.replace(day=1).strftime("%Y-%m-%d")
        for item in _list_dicts(spec.get("filters")):
            field_name = _text(item.get("tableau_field") or item.get("key"))
            if not field_name:
                continue
            context.filters.append(
                {
                    "筛选入口": field_name,
                    "类型": "筛选器",
                    "示例值/规则": _sample_text(_list(item.get("sample_values"))),
                    "使用方式": "--vf",
                    "使用边界": "筛选器使用 --vf；示例值只用于识别值域。",
                    "来源": "Tableau spec.filters",
                }
            )
        for item in _list_dicts(spec.get("parameters")):
            field_name = _text(item.get("tableau_field") or item.get("key"))
            if not field_name:
                continue
            context.parameters.append(
                {
                    "筛选入口": field_name,
                    "类型": "参数",
                    "示例值/规则": start_example,
                    "使用方式": "--vp",
                    "使用边界": "参数会改变 Tableau 计算或视图状态，不能写成 --vf。",
                    "来源": "Tableau spec.parameters",
                }
            )

    mapping_rows = _list_dicts(_map(mapping).get("mappings")) if mapping else []
    for row in mapping_rows:
        context.mappings.append(
            {
                "源字段": _text(row.get("view_field")),
                "类型": _text(row.get("type")),
                "标准语义": _text(row.get("standard_id")),
                "本地字段": _text(row.get("field_id_or_override")),
                "说明": _mapping_note(row),
            }
        )

    for question in _list(maintenance.get("pending_questions")):
        if isinstance(question, dict):
            topic = _text(question.get("field") or "待补齐主题")
            text = "；".join(part for part in [_text(question.get("question")), _text(question.get("reason"))] if part)
        else:
            topic = "待补齐主题"
            text = _text(question)
        if text:
            context.gaps.append(
                {
                    "优先级": "中",
                    "主题": topic,
                    "影响": "影响元数据完整性",
                    "当前缺口": text,
                    "补齐位置": f"metadata/datasets/{dataset_id}.yaml::maintenance.pending_questions",
                    "补齐后用途": "补齐报告边界和使用说明。",
                }
            )

    for name in _list_str(source_context.get("unresolved_dimensions")):
        context.gaps.append(
            {
                "优先级": "中",
                "主题": name,
                "影响": "影响标准语义匹配",
                "当前缺口": "mapping 待补齐",
                "补齐位置": "metadata/mappings/*.yaml",
                "补齐后用途": "可进入统一语义层。",
            }
        )

    if context.validation_state == "failed":
        context.boundaries.append({"边界/风险": "元数据校验失败", "说明": "validate 未通过", "对使用者的影响": "报告只能作为待修复清单。"})
    if context.description:
        context.boundaries.append({"边界/风险": "数据口径", "说明": context.description, "对使用者的影响": "只能按当前元数据描述解释数据。"})
    if connector == "duckdb":
        context.boundaries.append({"边界/风险": "样本值边界", "说明": "示例值来自只读采样", "对使用者的影响": "不能当作完整枚举清单。"})
        context.boundaries.append({"边界/风险": "registry 边界", "说明": "YAML 模式不反写 runtime registry", "对使用者的影响": "registry.db 不能作为业务口径来源。"})
    elif connector in {"mysql", "clickhouse"}:
        context.boundaries.append({"边界/风险": "registry 边界", "说明": "YAML 模式不反写 runtime registry", "对使用者的影响": "registry.db 不能作为业务口径来源。"})
        context.boundaries.append({"边界/风险": "凭据边界", "说明": "报告只展示 connection_ref、credential_ref 或 env 名称", "对使用者的影响": "真实密码、token、DSN 不进入 metadata 或报告。"})
    else:
        if not manifest:
            context.boundaries.append({"边界/风险": "导出字段边界", "说明": "未提供 manifest", "对使用者的影响": "无法证明实际 CSV 物理列。"})
        context.boundaries.append({"边界/风险": "Tableau 参数边界", "说明": "筛选器和参数使用不同接口", "对使用者的影响": "筛选器用 --vf，参数用 --vp。"})

    if connector_meta and connector == "duckdb":
        context.technical_rows.extend(
            [
                ("DuckDB 文件", _text(connector_meta.get("path") or connector_meta.get("db_path"))),
                ("Schema", _text(connector_meta.get("schema"))),
                ("对象", _text(connector_meta.get("object_name"))),
                ("对象类型", _text(connector_meta.get("object_kind"))),
            ]
        )
    if connector_meta and connector in {"mysql", "clickhouse"}:
        context.technical_rows.extend(
            [
                ("Database", _text(connector_meta.get("database"))),
                ("Schema", _text(connector_meta.get("schema"))),
                ("对象", _text(connector_meta.get("object_name") or connector_meta.get("table"))),
                ("对象类型", _text(connector_meta.get("object_kind"))),
                ("connection_ref", _connection_ref_text(connector_meta.get("connection_ref"))),
                ("credential_ref", _connection_ref_text(connector_meta.get("credential_ref"))),
                ("dsn_env", _connection_ref_text(connector_meta.get("dsn_env"))),
            ]
        )
    tableau = _map(entry.get("tableau"))
    if connector == "tableau":
        context.technical_rows.extend(
            [
                ("Workbook", _text(tableau.get("workbook_name"))),
                ("View", _text(tableau.get("view_name"))),
                ("View LUID", _text(tableau.get("view_luid"))),
                ("Content URL", _text(tableau.get("content_url"))),
            ]
        )
    context.technical_rows.extend(
        [
            ("数据源ID", dataset_id),
            ("报告生成时间", generated_at.strftime("%Y-%m-%d %H:%M:%S")),
            ("默认报告目录", _path_text(report_dir)),
        ]
    )

    context.metadata_sources.extend(
        [
            ("metadata/datasets/*.yaml", "数据集、字段、指标、粒度和适用边界", "作为报告元数据事实读取" if dataset else "未读取"),
            ("metadata/mappings/*.yaml", "源字段到标准语义的映射", "只作为映射读取，不替代字段/指标定义" if context.mappings else "未读取"),
            ("metadata/dictionaries/*.yaml", "公共术语、指标和维度定义", "只通过 business_definition.ref 追溯，不展开复制"),
            ("metadata/audit/*", "维护日志、ref 关联和 refine diff", "审计层隔离，不作为业务定义真源"),
        ]
    )

    if export_summary:
        view0 = ((export_summary.get("views") or [None])[0]) or {}
        context.export_rows.extend(
            [
                ("导出状态", "成功" if export_summary.get("success") else "失败"),
                ("导出时间", _text(export_summary.get("timestamp"))),
                ("导出文件", _text(view0.get("file_path"))),
            ]
        )
    if manifest:
        context.export_rows.append(("导出行数", _text(manifest.get("row_count"))))
        columns = _list_dicts(_map(manifest.get("schema")).get("columns"))
        context.export_rows.append(("导出列数", str(len(columns))))
        context.manifest_columns = [_text(column.get("name")) for column in columns if _text(column.get("name"))]

    return context


def _status(context: ReportContext) -> str:
    if context.validation_state == "failed":
        return "暂不建议用于正式分析"
    if context.gaps:
        return "可用但有待补齐"
    return "可用"


def _primary_risk(context: ReportContext) -> str:
    if context.validation_state == "failed":
        return "元数据校验未通过，需要先修复结构或定义。"
    if context.gaps:
        return f"存在 {len(context.gaps)} 个元数据待补齐项，相关口径不能直接用于正式结论。"
    if context.connector == "tableau" and not context.manifest_columns:
        return "未提供 manifest，无法证明实际导出物理列。"
    if context.connector == "duckdb":
        return "示例值来自只读采样，不代表完整枚举。"
    if context.connector in {"mysql", "clickhouse"}:
        return "正式取数必须从 runtime registry entry/spec 进入，并只允许已注册字段。"
    return "未发现显式待补齐项。"


def _scale_text(context: ReportContext) -> str:
    parts: list[str] = []
    row_count = ""
    for key, value in context.technical_rows:
        if key == "行数" and value:
            row_count = value
    if row_count:
        parts.append(f"{row_count} 行")
    if context.fields:
        parts.append(f"{len(context.fields)} 个字段")
    if context.metrics:
        parts.append(f"{len(context.metrics)} 个指标")
    count_filters = len(context.filters) + len(context.parameters)
    if count_filters:
        parts.append(f"{count_filters} 个筛选入口")
    if context.manifest_columns:
        parts.append(f"{len(context.manifest_columns)} 个导出物理列")
    return "，".join(parts)


def render_markdown(context: ReportContext) -> str:
    lines: list[str] = [f"# {_cell(context.display_name)} 元数据报告", ""]
    lines.extend(["## 1. 数据源结论", "", "| 项目 | 内容 |", "| --- | --- |"])
    connector_label = {"duckdb": "DuckDB", "tableau": "Tableau", "mysql": "MySQL", "clickhouse": "ClickHouse"}.get(context.connector, context.connector)
    data_type = connector_label if not context.object_kind else f"{connector_label} / {context.object_kind}"
    conclusion_rows = [
        ("数据源", context.display_name),
        ("数据类型", data_type),
        ("当前状态", _status(context)),
        ("数据规模", _scale_text(context)),
        ("主要用途", _join(context.suitable_for)),
        ("不能用于", _join(context.not_suitable_for)),
        ("最大风险", _primary_risk(context)),
        ("待补齐项", f"{len(context.gaps)} 项" if context.gaps else "无显式待补齐项"),
    ]
    for key, value in conclusion_rows:
        if value:
            lines.append(f"| {key} | {_cell(value)} |")
    lines.append("")

    if context.suitable_for or context.not_suitable_for:
        lines.extend(["## 2. 适用场景", ""])
        if context.suitable_for:
            lines.extend(["### 2.1 可以直接支持", "", "| 场景 | 元数据位置 |", "| --- | --- |"])
            for item in context.suitable_for:
                lines.append(f"| {_cell(item)} | {_code(f'metadata/datasets/{context.dataset_id}.yaml::business.suitable_for')} |")
            lines.append("")
        if context.not_suitable_for:
            lines.extend(["### 2.2 不建议用于", "", "| 场景 | 元数据位置 |", "| --- | --- |"])
            for item in context.not_suitable_for:
                lines.append(f"| {_cell(item)} | {_code(f'metadata/datasets/{context.dataset_id}.yaml::business.not_suitable_for')} |")
            lines.append("")

    if context.fields or context.metrics:
        lines.extend(["## 3. 核心字段与指标", ""])
        if context.fields:
            lines.extend(["### 3.1 核心字段", "", "| 名称 | 类型 | 业务含义 | 口径状态 | 定义位置 |", "| --- | --- | --- | --- | --- |"])
            for row in context.fields[:20]:
                lines.append(
                    f"| {_cell(row['名称'])} | {_cell(row['类型'])} | {_cell(row['业务含义'])} | "
                    f"{_cell(row['口径状态'])} | {_cell(row['定义位置'])} |"
                )
            lines.append("")
        if context.metrics:
            lines.extend(["### 3.2 核心指标", "", "| 指标 | 业务含义 | 计算或聚合方式 | 单位 | 适用粒度 | 口径状态 | 定义位置 |", "| --- | --- | --- | --- | --- | --- | --- |"])
            for row in context.metrics[:20]:
                lines.append(
                    f"| {_cell(row['指标'])} | {_cell(row['业务含义'])} | {_cell(row['计算或聚合方式'])} | "
                    f"{_cell(row['单位'])} | {_cell(row['适用粒度'])} | {_cell(row['口径状态'])} | {_cell(row['定义位置'])} |"
                )
            lines.append("")

    entries = [*context.filters, *context.parameters]
    if entries:
        lines.extend(["## 4. 筛选方式与常用入口", "", "| 筛选入口 | 类型 | 示例值/规则 | 使用方式 | 使用边界 |", "| --- | --- | --- | --- | --- |"])
        for row in entries:
            lines.append(
                f"| {_cell(row['筛选入口'])} | {_cell(row['类型'])} | {_cell(row['示例值/规则'])} | "
                f"{_code(row['使用方式'])} | {_cell(row['使用边界'])} |"
            )
        lines.append("")

    lines.extend(["## 5. 元数据补齐清单", ""])
    if context.gaps:
        lines.extend(["| 优先级 | 主题 | 影响 | 当前缺口 | 补齐位置 | 补齐后用途 |", "| --- | --- | --- | --- | --- | --- |"])
        for row in context.gaps:
            lines.append(
                f"| {_cell(row['优先级'])} | {_cell(row['主题'])} | {_cell(row['影响'])} | "
                f"{_cell(row['当前缺口'])} | {_code(row['补齐位置'])} | {_cell(row['补齐后用途'])} |"
            )
    else:
        lines.append("- 无显式待补齐项。")
    lines.append("")

    if context.boundaries:
        lines.extend(["## 6. 数据边界与风险", "", "| 边界/风险 | 说明 | 对使用者的影响 |", "| --- | --- | --- |"])
        for row in context.boundaries:
            lines.append(f"| {_cell(row['边界/风险'])} | {_cell(row['说明'])} | {_cell(row['对使用者的影响'])} |")
        lines.append("")

    if context.fields or context.metrics or entries:
        lines.extend(["## 7. 完整明细", ""])
        if context.fields:
            lines.extend(["### 7.1 字段明细", "", "| 名称 | 源字段 | 元数据类型 | 角色 | 业务定义 | 示例/规则 | 口径状态 | 定义位置 |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
            for row in context.fields:
                lines.append(
                    f"| {_cell(row['名称'])} | {_code(row['源字段'])} | {_cell(row['metadata类型'])} | {_cell(row['角色'])} | "
                    f"{_cell(row['业务含义'])} | {_cell(row['示例/规则'])} | {_cell(row['口径状态'])} | {_cell(row['定义位置'])} |"
                )
            lines.append("")
        if context.metrics:
            lines.extend(["### 7.2 指标明细", "", "| 指标 | 源字段/表达式 | 计算或聚合方式 | 单位 | 业务定义 | 适用粒度 | 口径状态 | 定义位置 |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
            for row in context.metrics:
                lines.append(
                    f"| {_cell(row['指标'])} | {_code(row['源字段/表达式'])} | {_cell(row['计算或聚合方式'])} | {_cell(row['单位'])} | "
                    f"{_cell(row['业务含义'])} | {_cell(row['适用粒度'])} | {_cell(row['口径状态'])} | {_cell(row['定义位置'])} |"
                )
            lines.append("")
        if entries:
            lines.extend(["### 7.3 筛选入口明细", "", "| 名称 | 类型 | 使用方式 | 示例值/规则 | 来源 |", "| --- | --- | --- | --- | --- |"])
            for row in entries:
                lines.append(f"| {_cell(row['筛选入口'])} | {_cell(row['类型'])} | {_code(row['使用方式'])} | {_cell(row['示例值/规则'])} | {_cell(row.get('来源'))} |")
            lines.append("")

    lines.extend(["## 8. 数据源使用说明", ""])
    if context.technical_rows:
        lines.extend(["| 项目 | 值 |", "| --- | --- |"])
        for key, value in context.technical_rows:
            if value:
                lines.append(f"| {_cell(key)} | {_code(value)} |")
        lines.append("")
    if context.connector in {"duckdb", "mysql", "clickhouse"} and context.filters:
        lines.extend(["| 业务筛选 | SQL 条件示例 | 注意事项 |", "| --- | --- | --- |"])
        for row in context.filters[:20]:
            source = next((field["源字段"] for field in context.fields if field["名称"] == row["筛选入口"]), "")
            condition = f'"{source}" = \'<value>\'' if source else "<field> = '<value>'"
            lines.append(f"| {_cell(row['筛选入口'])} | `{condition}` | 示例写法，正式值以实时数据为准。 |")
        lines.append("")
    if context.connector == "tableau" and entries:
        lines.extend(["| 类型 | 名称 | 示例 | 用途 |", "| --- | --- | --- | --- |"])
        for row in context.filters[:20]:
            lines.append(f"| 筛选器 | {_cell(row['筛选入口'])} | `--vf \"{row['筛选入口']}=<value>\"` | 控制 Tableau 视图筛选。 |")
        for row in context.parameters[:20]:
            lines.append(f"| 参数 | {_cell(row['筛选入口'])} | `--vp \"{row['筛选入口']}={row['示例值/规则']}\"` | 控制 Tableau 参数。 |")
        lines.append("")

    if context.metadata_sources or context.mappings or context.export_rows or context.manifest_columns:
        lines.extend(["## 9. 技术维护附录", ""])
        if context.metadata_sources:
            lines.extend(["### 9.1 输入与维护层边界", "", "| 层级 | 用途 | 报告处理 |", "| --- | --- | --- |"])
            for source, purpose, status in context.metadata_sources:
                lines.append(f"| `{source}` | {_cell(purpose)} | {_cell(status)} |")
            lines.append("")
        if context.mappings:
            lines.extend(["### 9.2 映射明细", "", "| 源字段 | 类型 | 标准语义 | 本地字段 | 说明 |", "| --- | --- | --- | --- | --- |"])
            for row in context.mappings:
                lines.append(f"| {_code(row['源字段'])} | {_cell(row['类型'])} | {_code(row['标准语义'])} | {_code(row['本地字段'])} | {_cell(row['说明'])} |")
            lines.append("")
        if context.export_rows:
            lines.extend(["### 9.3 导出验证", "", "| 项目 | 值 |", "| --- | --- |"])
            for key, value in context.export_rows:
                if value:
                    lines.append(f"| {_cell(key)} | {_code(value)} |")
            lines.append("")
        if context.manifest_columns:
            lines.extend(["### 9.4 实际导出物理列", ""])
            for index, column in enumerate(context.manifest_columns, start=1):
                lines.append(f"{index}. `{column}`")
            lines.append("")

    lines.extend(["## 10. 结论", ""])
    lines.append(f"- 当前状态：{_status(context)}。")
    if context.suitable_for:
        lines.append(f"- 可以优先用于：{_join(context.suitable_for)}。")
    if context.not_suitable_for:
        lines.append(f"- 暂不应用于：{_join(context.not_suitable_for)}。")
    if context.gaps:
        lines.append(f"- 下一步需要补齐：{_join([gap['主题'] for gap in context.gaps], limit=5)}。")
    else:
        lines.append("- 下一步需要补齐：无显式待补齐项。")
    return "\n".join(lines).rstrip() + "\n"
