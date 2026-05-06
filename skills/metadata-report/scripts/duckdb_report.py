#!/usr/bin/env python3
from __future__ import annotations

import csv
import shutil
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()
AGENTS_DIR = WORKSPACE_DIR / ".agents"
if (AGENTS_DIR / "skills").is_dir() and str(AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIR))

from runtime.tableau.sqlite_store import list_entries, load_spec_by_entry_key  # noqa: E402
from skills.metadata.lib.metadata_io import (  # noqa: E402
    MetadataError,
    iter_dataset_files,
    load_dataset_file,
    load_mapping_file,
    normalize_dataset,
    resolve_dataset_path,
)
from skills.metadata.lib.value_patterns import clean_sample_values, infer_value_pattern  # noqa: E402
from skills.metadata.scripts.validate_metadata import validate_dataset  # noqa: E402


def default_report_dir(workspace: Path) -> Path:
    return workspace / "metadata" / "sync" / "duckdb" / "reports"


def build_report_filename(source_id: str, *, generated_at: datetime, report_kind: str = "sync") -> str:
    timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{source_id}_{report_kind}_report.md"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_list_dicts(value: Any) -> list[dict[str, Any]]:
    return [x for x in _safe_list(value) if isinstance(x, dict)]


def _safe_list_str(value: Any) -> list[str]:
    return [str(x) for x in _safe_list(value) if isinstance(x, str) and x]


def _safe_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _display(value: Any) -> str:
    if value is None or value == "":
        return "未配置"
    if isinstance(value, list):
        return "、".join(str(item) for item in value) if value else "未配置"
    return str(value)


def _cell(value: Any) -> str:
    return _display(value).replace("|", "\\|").replace("\n", " ")


def _code(value: Any) -> str:
    return f"`{_cell(value)}`"


def _quote_ident(value: Any) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _resolve_duckdb_path(path_value: Any) -> Path | None:
    if not path_value:
        return None
    path = Path(str(path_value)).expanduser()
    if not path.is_absolute():
        path = WORKSPACE_DIR / path
    return path


def _duckdb_relation(duckdb_meta: dict[str, Any]) -> str | None:
    object_name = duckdb_meta.get("object_name")
    if not object_name:
        return None
    schema = duckdb_meta.get("schema")
    if schema:
        return f"{_quote_ident(schema)}.{_quote_ident(object_name)}"
    return _quote_ident(object_name)


def _format_sample_values(values: list[Any]) -> str:
    cleaned = clean_sample_values(values)
    return "、".join(cleaned) if cleaned else "当前无非空样本"


def _format_sample_values_with_pattern(values: list[Any]) -> str:
    pattern = infer_value_pattern(values)
    if pattern:
        return f"{pattern['example']}（正则：`{pattern['regex']}`）"
    return _format_sample_values(values)


def _sample_values_for_field(samples: dict[str, list[Any]], source_field: Any) -> list[Any]:
    key = str(source_field)
    return samples.get(key) or samples.get("__error__") or []


def _sample_cell_for_field(field: dict[str, Any], samples: dict[str, list[Any]]) -> str:
    if field.get("role") not in {"dimension", "time_dimension"}:
        return "不适用：非筛选维度"
    source_field = field.get("source_field") or field.get("physical_name") or field.get("name")
    return _format_sample_values_with_pattern(_sample_values_for_field(samples, source_field))


def _sampled_field_count(samples: dict[str, list[Any]]) -> int:
    count = 0
    for key, values in samples.items():
        if key == "__error__" or not values:
            continue
        sample_text = _format_sample_values(values)
        if sample_text == "当前无非空样本" or sample_text.startswith("未采样："):
            continue
        count += 1
    return count


def _import_duckdb_module() -> Any | None:
    existing = sys.modules.get("duckdb")
    if existing is not None and hasattr(existing, "connect"):
        return existing

    original_path = list(sys.path)
    if existing is not None:
        sys.modules.pop("duckdb", None)
    try:
        workspace_resolved = WORKSPACE_DIR.resolve()
        filtered_path: list[str] = []
        for item in sys.path:
            if not item:
                continue
            try:
                if Path(item).resolve() == workspace_resolved:
                    continue
            except OSError:
                pass
            filtered_path.append(item)
        sys.path = filtered_path

        import importlib

        module = importlib.import_module("duckdb")
        return module if hasattr(module, "connect") else None
    except ImportError:
        return None
    finally:
        sys.path = original_path


def _collect_duckdb_sample_values(dataset: dict[str, Any], fields: list[dict[str, Any]], *, limit: int = 8) -> dict[str, list[Any]]:
    duckdb_meta = _duckdb_meta(dataset)
    db_path = _resolve_duckdb_path(duckdb_meta.get("path"))
    relation = _duckdb_relation(duckdb_meta)
    if not db_path or not db_path.exists() or not relation:
        return {"__error__": ["未采样：数据库不可访问"]}

    duckdb_module = _import_duckdb_module()
    duckdb_cli = shutil.which("duckdb")
    if duckdb_module is None and not duckdb_cli:
        return {"__error__": ["未采样：DuckDB Python 模块不可用"]}

    samples: dict[str, list[Any]] = {}
    con: Any | None = None
    try:
        if duckdb_module is not None:
            con = duckdb_module.connect(str(db_path), read_only=True)
    except Exception:
        con = None
        if not duckdb_cli:
            return {"__error__": ["未采样：数据库不可访问"]}
    try:
        for field in fields:
            if field.get("role") not in {"dimension", "time_dimension"}:
                continue
            source_field = field.get("source_field") or field.get("physical_name") or field.get("name")
            if not source_field:
                continue
            sql = (
                f"SELECT DISTINCT CAST({_quote_ident(source_field)} AS VARCHAR) AS sample_value "
                f"FROM {relation} "
                f"WHERE {_quote_ident(source_field)} IS NOT NULL "
                f"LIMIT {int(limit)}"
            )
            try:
                if con is not None:
                    values = [row[0] for row in con.execute(sql).fetchall()]
                elif duckdb_cli:
                    result = subprocess.run(
                        [duckdb_cli, "-readonly", str(db_path), "-csv", "-c", sql],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    reader = csv.DictReader(result.stdout.splitlines())
                    values = [row.get("sample_value") for row in reader]
                else:
                    values = ["未采样：DuckDB Python 模块不可用"]
            except Exception:
                values = ["未采样：字段不存在或查询失败"]
            samples[str(source_field)] = values
    finally:
        if con is not None:
            con.close()
    return samples


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
    definition = _definition(item)
    return str(definition.get("source_type") or item.get("definition_source") or "未配置")


def _review_text(item: dict[str, Any]) -> str:
    definition = _definition(item)
    source_text = _review_source_text(item)
    if definition.get("needs_review") is True:
        return f"待确认：{source_text}；需补业务定义"
    if definition.get("needs_review") is False:
        return f"已确认：{source_text}"
    return "未配置"


def _evidence_sources(item: dict[str, Any]) -> list[str]:
    definition = _definition(item)
    evidence = definition.get("source_evidence") or item.get("source_evidence") or []
    sources: list[str] = []
    for record in _safe_list_dicts(evidence):
        source = record.get("source")
        if isinstance(source, str) and source and source not in sources:
            sources.append(source)
            continue
        evidence_type = record.get("type")
        evidence_value = record.get("value") or record.get("quote")
        if evidence_type and evidence_value:
            label = f"{evidence_type}:{evidence_value}"
            if label not in sources:
                sources.append(label)
    return sources


def _evidence_cell(item: dict[str, Any]) -> str:
    sources = _evidence_sources(item)
    return _cell("；".join(sources)) if sources else "未配置"


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
    if "duckdb_ho_schema_snapshot" in source:
        return "DuckDB schema"
    if source.startswith("duckdb.") or source.startswith("tableau."):
        return "mapping"
    return Path(source).name or source


def _review_source_text(item: dict[str, Any]) -> str:
    labels: list[str] = []
    for source in _evidence_sources(item):
        label = _source_label(source)
        if label and label not in labels:
            labels.append(label)
    return "、".join(labels[:3]) if labels else "来源未配置"


def _append_column_notes(lines: list[str], notes: list[tuple[str, str]]) -> None:
    lines.append("表头说明：")
    lines.append("")
    lines.append("| 表头 | 含义 |")
    lines.append("| --- | --- |")
    for name, meaning in notes:
        lines.append(f"| `{name}` | {meaning} |")
    lines.append("")


FIELD_COLUMN_NOTES = [
    ("展示名", "报告中给业务用户看的字段名称。"),
    ("源字段", "DuckDB 对象里的真实列名。"),
    ("DuckDB 类型", "DuckDB schema 中记录的原始字段类型。"),
    ("metadata 类型", "metadata 归一后的类型，用于分析上下文。"),
    ("角色", "字段在分析中的用途，例如维度、时间字段或指标候选。"),
    ("业务定义", "已确认的业务口径；没有真实定义时只写业务定义待确认。"),
    ("定义来源", "定义来自字典、映射覆盖或 pending 待确认状态。"),
    ("示例/规则", "筛选候选字段的样例值或格式规则；不是完整枚举。"),
    ("证据", "支撑该字段说明的真实 YAML、source 或采样材料。"),
    ("Review", "是否可作为确认口径，以及对应真实来源。"),
]


METRIC_COLUMN_NOTES = [
    ("指标", "报告中给业务用户看的指标名称。"),
    ("源字段", "指标对应的 DuckDB 原始列名。"),
    ("表达式", "metadata 记录的指标取数字段或计算表达式。"),
    ("聚合方式", "默认汇总方式，例如 sum、avg 或 weighted_avg。"),
    ("单位", "指标单位；没有事实时显示未配置。"),
    ("业务定义", "已确认的业务口径；没有真实定义时只写业务定义待确认。"),
    ("定义来源", "定义来自字典、映射覆盖或 pending 待确认状态。"),
    ("证据", "支撑该指标说明的真实 YAML、source 或采样材料。"),
    ("Review", "是否可作为确认口径，以及对应真实来源。"),
]


FILTER_COLUMN_NOTES = [
    ("字段", "可用于 DuckDB 筛选的真实列名。"),
    ("显示名", "报告中给业务用户看的字段名称。"),
    ("应用方式", "后续取数时使用的筛选参数或 SQL 表达方式。"),
    ("可选值/示例/规则", "当前只读采样得到的示例值或格式规则，不代表完整枚举。"),
    ("说明", "该筛选字段的使用边界。"),
]


MAPPING_COLUMN_NOTES = [
    ("源字段", "数据源中的真实字段名。"),
    ("类型", "该映射对应 metric、dimension 或 field。"),
    ("标准 ID", "映射到公共语义字典的 ID；source_specific 表示没有公共标准。"),
    ("字段 ID/覆盖", "源字段本地 ID 或覆盖字段名，不等同于公共标准。"),
    ("说明", "来自 mapping 的人工说明；无真实定义时只提示待补充。"),
]


def _field_source_name(field: dict[str, Any]) -> str:
    for key in ("source_field", "physical_name", "name"):
        value = _safe_text(field.get(key))
        if value:
            return value
    return ""


def _metric_source_names(metric: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for value in (
        metric.get("source_field"),
        _safe_mapping(metric.get("source_mapping")).get("view_field"),
    ):
        text = _safe_text(value)
        if text and text not in names:
            names.append(text)
    return names


def _metric_source_name(metric: dict[str, Any]) -> str:
    names = _metric_source_names(metric)
    return names[0] if names else ""


def _metric_lookup_by_source(metrics: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for metric in metrics:
        for source_name in _metric_source_names(metric):
            lookup.setdefault(source_name, metric)
    return lookup


def _metric_for_field(field: dict[str, Any], metric_lookup: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    source_name = _field_source_name(field)
    return metric_lookup.get(source_name) if source_name else None


def _mapping_note(row: dict[str, Any]) -> str:
    note = str(row.get("definition_override") or row.get("notes") or "").strip()
    if not note:
        return "未配置"
    pending_markers = ["待确认", "需确认", "具体业务口径", "作为指标候选"]
    if any(marker in note for marker in pending_markers):
        return "业务定义待确认"
    return note


def _source_type(dataset: dict[str, Any]) -> str:
    summary = _safe_mapping(dataset.get("source_summary"))
    if summary.get("type"):
        return str(summary["type"])
    duckdb_meta = _safe_mapping(_safe_mapping(dataset.get("source")).get("duckdb"))
    return "duckdb_view" if duckdb_meta.get("object_kind") == "view" else "duckdb_table"


def _duckdb_meta(dataset: dict[str, Any]) -> dict[str, Any]:
    source = _safe_mapping(dataset.get("source"))
    duckdb_meta = _safe_mapping(source.get("duckdb"))
    catalog = _safe_mapping(dataset.get("catalog_summary"))
    object_kind = duckdb_meta.get("object_kind") or catalog.get("object_kind")
    if not object_kind and source.get("connector") == "duckdb":
        object_kind = "base table"
    return {
        "path": duckdb_meta.get("path") or duckdb_meta.get("db_path") or catalog.get("db_path"),
        "schema": duckdb_meta.get("schema") or catalog.get("schema"),
        "object_name": duckdb_meta.get("object_name") or catalog.get("object_name"),
        "object_kind": object_kind,
        "row_count": catalog.get("row_count"),
        "column_count": catalog.get("column_count"),
    }


def _pending_questions(value: Any) -> list[str]:
    questions: list[str] = []
    for item in _safe_list(value):
        if isinstance(item, str) and item:
            questions.append(item)
        elif isinstance(item, dict):
            field = item.get("field")
            question = item.get("question")
            reason = item.get("reason")
            parts = []
            if field:
                parts.append(f"`{field}`")
            if question:
                parts.append(str(question))
            if reason:
                parts.append(f"原因：{reason}")
            if parts:
                questions.append("；".join(parts))
    return questions


def _role_counts(fields: list[dict[str, Any]]) -> tuple[int, int, int]:
    dimension_roles = {"dimension", "time_dimension"}
    measure_roles = {"metric_source", "measure_candidate"}
    dimensions = sum(1 for field in fields if field.get("role") in dimension_roles)
    measures = sum(1 for field in fields if field.get("role") in measure_roles)
    filters = dimensions
    return dimensions, measures, filters


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


def _load_targets(*, key: str | None, all_entries: bool) -> list[dict[str, Any]]:
    entries = [e for e in list_entries(active_only=not all_entries) if isinstance(e, dict) and e.get("source_backend") == "duckdb"]
    if key:
        return [e for e in entries if e.get("key") == key or e.get("source_id") == key]
    if all_entries:
        return entries
    return []


def _load_yaml_dataset(workspace: Path, dataset_id: str) -> dict[str, Any]:
    path = resolve_dataset_path(workspace, dataset_id)
    data = normalize_dataset(load_dataset_file(path), path=path)
    source = _safe_mapping(data.get("source"))
    if source.get("connector") != "duckdb":
        raise MetadataError(f"{dataset_id!r} is not a DuckDB dataset")
    return data


def _load_yaml_dataset_if_exists(workspace: Path, dataset_id: str) -> dict[str, Any] | None:
    if not dataset_id:
        return None
    try:
        return _load_yaml_dataset(workspace, dataset_id)
    except MetadataError:
        return None


def _load_yaml_datasets(workspace: Path, *, dataset_id: str | None, all_yaml: bool) -> list[dict[str, Any]]:
    if dataset_id:
        return [_load_yaml_dataset(workspace, dataset_id)]
    if not all_yaml:
        return []
    datasets: list[dict[str, Any]] = []
    for path in iter_dataset_files(workspace):
        data = normalize_dataset(load_dataset_file(path), path=path)
        if _safe_mapping(data.get("source")).get("connector") == "duckdb":
            datasets.append(data)
    return datasets


def _load_dataset_mapping(workspace: Path, dataset: dict[str, Any]) -> dict[str, Any] | None:
    mapping_ref = str(dataset.get("mapping_ref") or "").strip()
    if not mapping_ref:
        return None
    path = workspace / "metadata" / "mappings" / f"{mapping_ref}.yaml"
    if not path.exists():
        return None
    return load_mapping_file(path)


def _validate_yaml_datasets(workspace: Path, datasets: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for dataset in datasets:
        dataset_id = str(dataset.get("id") or dataset.get("source_id") or "")
        try:
            path = resolve_dataset_path(workspace, dataset_id)
        except MetadataError as exc:
            errors.append(str(exc))
            continue
        errors.extend(validate_dataset(dataset, path=path))
    return errors


def render_sync_report(
    *,
    entry: dict[str, Any],
    spec: dict[str, Any],
    generated_at: datetime,
    report_dir: Path,
    sync_mode: str,
    step_results: dict[str, str],
) -> str:
    duckdb_meta = entry.get("duckdb") if isinstance(entry.get("duckdb"), dict) else {}
    semantics = entry.get("semantics") if isinstance(entry.get("semantics"), dict) else {}
    dimensions = _safe_list_dicts(spec.get("dimensions"))
    measures = _safe_list_dicts(spec.get("measures"))
    filters = _safe_list_dicts(spec.get("filters"))

    validate_state = step_results.get("validate")
    ready_status = "可用" if validate_state == "success" else "暂不建议用于正式分析" if validate_state == "failed" else "可用但未完成校验"
    suitable_for = _safe_list_str(semantics.get("suitable_for"))
    not_suitable_for = _safe_list_str(semantics.get("not_suitable_for"))
    grain = _safe_list_str(semantics.get("grain"))
    time_fields = _safe_list_str(semantics.get("time_fields"))
    field_count = len(_safe_list_str(entry.get("fields")))

    lines: list[str] = []
    lines.append(f"# {_cell(entry.get('display_name') or 'DuckDB 数据源')} 元数据报告")
    lines.append("")
    lines.append("## 1. 数据源结论")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("| --- | --- |")
    lines.append(f"| 数据源 | {_cell(entry.get('display_name'))} |")
    lines.append(f"| 数据类型 | DuckDB / {_cell(duckdb_meta.get('object_kind'))} |")
    lines.append(f"| 当前状态 | {ready_status} |")
    lines.append(f"| 数据规模 | {field_count} 个字段，{len(measures)} 个指标，{len(filters)} 个筛选入口 |")
    lines.append(f"| 主要用途 | {_cell(_short_list(suitable_for))} |")
    lines.append(f"| 不能用于 | {_cell(_short_list(not_suitable_for))} |")
    lines.append("| 最大风险 | 旧 runtime registry 报告缺少完整 YAML 业务定义，不能替代 metadata YAML 报告。 |")
    lines.append("| 待确认项 | 以 metadata YAML / mapping YAML 的 review 状态为准 |")
    lines.append("")

    lines.append("## 2. 业务适用场景")
    lines.append("")
    lines.append("### 2.1 可以直接支持")
    lines.append("")
    for item in suitable_for or ["未配置明确适用场景"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### 2.2 可以使用，但需要先确认口径")
    lines.append("")
    lines.append("- 旧 runtime registry 报告只说明运行结构；正式口径应补齐或读取 metadata YAML。")
    lines.append("")
    lines.append("### 2.3 不建议用于")
    lines.append("")
    for item in not_suitable_for or ["未配置不适用场景"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 3. 核心字段与指标速查")
    lines.append("")
    lines.append("### 3.1 常用字段")
    lines.append("")
    if dimensions:
        lines.append("| 名称 | 类型 | 业务含义 | 常见用途 | 口径状态 | 使用提醒 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for item in dimensions[:20]:
            lines.append(f"| {_cell(item.get('name'))} | 维度 | 业务定义待确认 | 用于筛选、分组和下钻 | 待确认 | 建议补齐 metadata YAML。 |")
    else:
        lines.append("- 无维度字段。")
    lines.append("")
    lines.append("### 3.2 常用指标")
    lines.append("")
    if measures:
        lines.append("| 指标 | 业务含义 | 计算或聚合方式 | 单位 | 适用粒度 | 口径状态 | 使用提醒 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for item in measures[:20]:
            lines.append(f"| {_cell(item.get('name'))} | 业务定义待确认 | DuckDB 字段 | 未配置 | {_cell(_short_list(grain))} | 待确认 | 建议补齐 metadata YAML。 |")
    else:
        lines.append("- 无指标。")
    lines.append("")

    lines.append("## 4. 筛选方式与常用入口")
    lines.append("")
    if filters:
        lines.append("| 筛选入口 | 类型 | 示例值/规则 | 使用方式 | 使用提醒 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for item in filters:
            lines.append(f"| {_cell(item.get('display_name') or item.get('key'))} | DuckDB 筛选字段 | 未采样 | {_code(item.get('apply_via') or 'sql_where')} | 正式值以实时数据为准。 |")
    else:
        lines.append("- 无筛选器。")
    lines.append("")

    lines.append("## 5. 重点口径确认清单")
    lines.append("")
    lines.append("- 该报告来自旧 runtime registry 路径，待确认项需要回到 metadata YAML / mapping YAML 中维护。")
    lines.append("")

    lines.append("## 6. 数据边界与风险")
    lines.append("")
    lines.append("| 边界/风险 | 说明 | 对使用者的影响 |")
    lines.append("| --- | --- | --- |")
    lines.append("| 业务定义边界 | runtime registry 只说明运行时结构 | 不能作为最终业务口径来源。 |")
    lines.append(f"| 校验状态 | {ready_status} | 校验失败时需要先修复 registry/spec。 |")
    lines.append("")

    lines.append("## 7. 完整字段与指标明细")
    lines.append("")
    lines.append("### 7.1 字段明细")
    lines.append("")
    if dimensions:
        lines.append("| 名称 | 源字段 | 类型 | 角色 | 业务定义 | 示例/规则 | 口径状态 | 来源摘要 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for item in dimensions:
            lines.append(f"| {_cell(item.get('name'))} | {_code(item.get('name'))} | {_code(item.get('data_type'))} | dimension | 业务定义待确认 | 未采样 | 待确认 | runtime registry |")
    else:
        lines.append("- 无维度字段。")
    lines.append("")
    lines.append("### 7.2 指标明细")
    lines.append("")
    if measures:
        lines.append("| 指标 | 源字段/表达式 | 聚合方式 | 单位 | 业务定义 | 适用粒度 | 口径状态 | 来源摘要 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for item in measures:
            lines.append(f"| {_cell(item.get('name'))} | {_code(item.get('name'))} | 未配置 | 未配置 | 业务定义待确认 | {_cell(_short_list(grain))} | 待确认 | runtime registry |")
    else:
        lines.append("- 无指标。")
    lines.append("")
    lines.append("### 7.3 筛选器明细")
    lines.append("")
    if filters:
        lines.append("| 名称 | 类型 | 字段/参数 | 可选值/规则 | 是否必填 | 口径状态 | 来源摘要 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for item in filters:
            lines.append(f"| {_cell(item.get('display_name') or item.get('key'))} | DuckDB 筛选字段 | {_code(item.get('key'))} | 未采样 | 否 | 仅结构可用 | runtime registry |")
    else:
        lines.append("- 无筛选器。")
    lines.append("")

    lines.append("## 8. Connector 使用说明")
    lines.append("")
    lines.append("### 8.1 DuckDB 使用说明")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    lines.append(f"| DuckDB 文件 | {_code(duckdb_meta.get('db_path'))} |")
    lines.append(f"| Schema | {_code(duckdb_meta.get('schema'))} |")
    lines.append(f"| 对象 | {_code(duckdb_meta.get('object_name'))} |")
    lines.append(f"| 对象类型 | {_code(duckdb_meta.get('object_kind'))} |")
    lines.append("| 查询边界 | runtime registry 同步说明，非 YAML 业务口径报告 |")
    lines.append("")
    lines.append("### 8.2 Tableau 使用说明")
    lines.append("")
    lines.append("- 无。该报告为 DuckDB 数据源报告。")
    lines.append("")

    lines.append("## 9. 技术维护附录")
    lines.append("")
    lines.append("### 9.1 注册与生成信息")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    rows = [
        ("source_id / dataset_id", entry.get("source_id")),
        ("key", entry.get("key")),
        ("type", entry.get("type")),
        ("status", entry.get("status")),
        ("category", entry.get("category")),
        ("报告生成时间", generated_at.strftime("%Y-%m-%d %H:%M:%S %Z")),
        ("默认报告目录", str(report_dir)),
        ("执行链路", "register -> sync_registry -> validate -> generate_report"),
        ("步骤状态", f"register={step_results.get('register', 'unknown')}, registry={step_results.get('registry', 'unknown')}, validate={step_results.get('validate', 'unknown')}"),
    ]
    for key, value in rows:
        lines.append(f"| `{_cell(key)}` | {_code(value)} |")
    lines.append("")
    lines.append("### 9.2 Metadata 来源")
    lines.append("")
    lines.append("| 来源 | 用途 | 状态 |")
    lines.append("| --- | --- | --- |")
    lines.append("| runtime registry | 运行时结构 | 已读取 |")
    lines.append("| metadata YAML | 业务定义、字段、指标、粒度和适用边界 | 未在该路径读取 |")
    lines.append("")
    lines.append("### 9.3 映射明细")
    lines.append("")
    lines.append("- 旧 runtime registry 路径不展开 mapping 明细。")
    lines.append("")
    lines.append("### 9.4 校验结果")
    lines.append("")
    lines.append("| 校验项 | 结果 | 说明 |")
    lines.append("| --- | --- | --- |")
    lines.append(f"| registry/spec validate | {ready_status} | 该结果只说明运行结构，不确认业务口径。 |")
    lines.append("")

    lines.append("## 10. 结论")
    lines.append("")
    lines.append(f"- 这份 DuckDB runtime metadata 当前状态：{ready_status}。")
    lines.append(f"- 可以优先用于：{_short_list(suitable_for)}。")
    lines.append(f"- 暂不应用于：{_short_list(not_suitable_for)}。")
    lines.append("- 下一步需要确认：补齐或读取 metadata YAML 后再作为业务口径材料。")
    lines.append("")

    return "\n".join(lines) + "\n"


def render_yaml_metadata_report(
    *,
    dataset: dict[str, Any],
    mapping: dict[str, Any] | None,
    generated_at: datetime,
    report_dir: Path,
    step_results: dict[str, str],
) -> str:
    dataset_id = str(dataset.get("id") or dataset.get("source_id") or "")
    business = _safe_mapping(dataset.get("business"))
    maintenance = _safe_mapping(dataset.get("maintenance"))
    summary = _safe_mapping(dataset.get("source_summary"))
    source = _safe_mapping(dataset.get("source"))
    duckdb_meta = _duckdb_meta(dataset)
    fields = _safe_list_dicts(dataset.get("fields"))
    metrics = _safe_list_dicts(dataset.get("metrics"))
    dimensions, measures, filters = _role_counts(fields)
    sample_values = _collect_duckdb_sample_values(dataset, fields)
    mapping_rows = _safe_list_dicts(_safe_mapping(mapping).get("mappings")) if mapping else []
    metric_lookup = _metric_lookup_by_source(metrics)
    review_fields = [
        field
        for field in fields
        if _metric_for_field(field, metric_lookup) is None and _definition(field).get("needs_review") is True
    ]
    review_metrics = [metric for metric in metrics if _definition(metric).get("needs_review") is True]

    display_name = _display(dataset.get("display_name"))
    suitable_for = _safe_list_str(business.get("suitable_for"))
    not_suitable_for = _safe_list_str(business.get("not_suitable_for"))
    grain = _safe_list_str(business.get("grain"))
    time_fields = _safe_list_str(business.get("time_fields"))
    filterable_fields = [field for field in fields if field.get("role") in {"dimension", "time_dimension"}]
    pending_questions = _pending_questions(maintenance.get("pending_questions"))
    review_count = len(review_fields) + len(review_metrics)
    validate_state = step_results.get("validate")
    if validate_state == "failed":
        ready_status = "暂不建议用于正式分析"
        primary_risk = "`metadata validate` 未通过，需要先修复定义或结构问题"
    elif review_count or pending_questions:
        ready_status = "可用但有待确认"
        primary_risk = "存在待确认字段或指标，相关口径不能直接用于正式结论"
    else:
        ready_status = "可用"
        primary_risk = "示例值来自只读采样，不代表完整枚举"

    lines: list[str] = []
    lines.append(f"# {display_name} 元数据报告")
    lines.append("")
    lines.append("## 1. 数据源结论")
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("| --- | --- |")
    lines.append(f"| 数据源 | {display_name} |")
    lines.append(f"| 数据类型 | DuckDB / {_cell(duckdb_meta.get('object_kind') or _source_type(dataset))} |")
    lines.append(f"| 当前状态 | {ready_status} |")
    lines.append(
        f"| 数据规模 | {_cell(duckdb_meta.get('row_count'))} 行，{len(fields)} 个字段，{len(metrics)} 个指标，{len(filterable_fields)} 个筛选入口 |"
    )
    lines.append(f"| 主要用途 | {_cell(_short_list(suitable_for))} |")
    lines.append(f"| 不能用于 | {_cell(_short_list(not_suitable_for))} |")
    lines.append(f"| 最大风险 | {_cell(primary_risk)} |")
    lines.append(f"| 待确认项 | {len(review_fields)} 个字段，{len(review_metrics)} 个指标 |")
    lines.append("")
    lines.append("本报告说明这份 DuckDB 数据源的 metadata 设计、字段和指标口径、筛选方式、来源依据和待确认问题。它不输出经营分析结论，只说明这份数据能怎样被可靠使用。")
    lines.append("")

    lines.append("## 2. 业务适用场景")
    lines.append("")
    lines.append("### 2.1 可以直接支持")
    lines.append("")
    if suitable_for:
        lines.append("| 场景 | 可用依据 | 使用提醒 |")
        lines.append("| --- | --- | --- |")
        basis = f"{len(fields)} 个字段、{len(metrics)} 个指标、粒度：{_short_list(grain)}"
        for item in suitable_for:
            lines.append(f"| {_cell(item)} | {_cell(basis)} | 先按第 3、4 章选择字段、指标和筛选入口。 |")
    else:
        lines.append("- 未配置明确适用场景。")
    lines.append("")
    lines.append("### 2.2 可以使用，但需要先确认口径")
    lines.append("")
    if review_fields or review_metrics or pending_questions:
        lines.append("| 场景 | 当前缺口 | 确认后可支持什么 |")
        lines.append("| --- | --- | --- |")
        for metric in review_metrics[:10]:
            lines.append(
                f"| {_cell(metric.get('display_name') or metric.get('name'))} 相关分析 | 指标业务定义待确认 | 可作为确定指标进入正式分析口径。 |"
            )
        for field in review_fields[:10]:
            lines.append(
                f"| {_cell(field.get('display_name') or field.get('name'))} 相关筛选或分组 | 字段业务定义待确认 | 可作为稳定维度进入分析上下文。 |"
            )
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
        lines.append("- 未配置不适用场景；正式分析前仍需核对数据口径。")
    lines.append("")

    lines.append("## 3. 核心字段与指标速查")
    lines.append("")
    lines.append("### 3.1 常用字段")
    lines.append("")
    core_fields = [field for field in fields if field.get("role") in {"time_dimension", "dimension"}][:20]
    if core_fields:
        lines.append("| 名称 | 类型 | 业务含义 | 常见用途 | 口径状态 | 使用提醒 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for field in core_fields:
            definition_item = _metric_for_field(field, metric_lookup) or field
            lines.append(
                f"| {_cell(field.get('display_name') or field.get('name'))} | {_cell(_field_kind(field))} | "
                f"{_cell(_definition_text(definition_item))} | {_cell(_field_usage(field))} | "
                f"{_cell(_definition_status(definition_item))} | 示例值不是完整枚举。 |"
            )
    else:
        lines.append("- 无核心维度字段。")
    lines.append("")
    lines.append("### 3.2 常用指标")
    lines.append("")
    if metrics:
        lines.append("| 指标 | 业务含义 | 计算或聚合方式 | 单位 | 适用粒度 | 口径状态 | 使用提醒 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for metric in metrics[:20]:
            aggregation = metric.get("aggregation") or metric.get("expression") or _metric_source_name(metric)
            lines.append(
                f"| {_cell(metric.get('display_name') or metric.get('name'))} | {_cell(_definition_text(metric))} | "
                f"{_cell(aggregation)} | {_cell(metric.get('unit'))} | {_cell(_short_list(grain))} | "
                f"{_cell(_definition_status(metric))} | 待确认指标不能直接用于正式结论。 |"
            )
    else:
        lines.append("- 无指标。该数据源按 lookup 维表注册，只提供维度补充，不直接提供业务指标。")
    lines.append("")

    lines.append("## 4. 筛选方式与常用入口")
    lines.append("")
    lines.append("| 筛选入口 | 类型 | 示例值/规则 | 使用方式 | 使用提醒 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for field in filterable_fields[:30]:
        source_field = field.get("source_field") or field.get("physical_name") or field.get("name")
        sample_cell = _format_sample_values_with_pattern(_sample_values_for_field(sample_values, source_field))
        lines.append(
            f"| {_cell(field.get('display_name') or field.get('name'))} | {_cell(_field_kind(field))} | "
            f"{_cell(sample_cell)} | `sql_where` | 按 {_code(source_field)} 过滤；样例来自只读采样。 |"
        )
    if not filterable_fields:
        lines.append("| 未配置 | 未配置 | 未配置 | 未配置 | 无已注册筛选候选字段。 |")
    lines.append("")
    lines.append("示例值只用于帮助识别字段值域，不代表完整枚举。DuckDB 数据源没有 Tableau 参数；正式取数筛选应通过 `sql_where` 或 data-export 的 DuckDB 筛选参数表达。")
    lines.append("")

    lines.append("## 5. 重点口径确认清单")
    lines.append("")
    if review_fields or review_metrics or pending_questions:
        lines.append("| 优先级 | 主题 | 影响 | 当前问题 | 建议确认对象/材料 | 确认后用途 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for metric in review_metrics:
            name = metric.get("display_name") or metric.get("name")
            lines.append(f"| 高 | {_cell(name)} | 影响指标解释和汇总口径 | 业务定义待确认 | 业务字典或指标负责人 | 可进入正式指标口径。 |")
        for field in review_fields:
            name = field.get("display_name") or field.get("name")
            lines.append(f"| 中 | {_cell(name)} | 影响筛选、分组或字段解释 | 业务定义待确认 | 数据源 owner 或口径文档 | 可作为稳定维度使用。 |")
        for question in pending_questions:
            lines.append(f"| 中 | 待确认主题 | 影响 metadata 完整性 | {_cell(question)} | 数据源 owner 或业务口径材料 | 补齐报告边界和使用说明。 |")
    else:
        lines.append("- 无显式待确认字段或指标。")
    lines.append("")

    lines.append("## 6. 数据边界与风险")
    lines.append("")
    lines.append("| 边界/风险 | 说明 | 对使用者的影响 |")
    lines.append("| --- | --- | --- |")
    lines.append(f"| 数据口径 | {_cell(dataset.get('description') or business.get('description') or '未配置业务描述')} | 只能按当前 metadata 描述解释数据。 |")
    lines.append("| 样本值边界 | 示例值来自报告生成时的 DuckDB 只读采样 | 不能当作完整枚举清单。 |")
    lines.append("| registry 边界 | YAML 模式下未反写 runtime registry | `registry.db` 不能作为业务口径来源。 |")
    validate_text = "通过" if validate_state == "success" else "失败" if validate_state == "failed" else "未执行"
    lines.append(f"| 校验状态 | metadata validate {validate_text} | 失败时报告只能作为待修复清单。 |")
    lines.append("")

    lines.append("## 7. 完整字段与指标明细")
    lines.append("")
    lines.append("### 7.1 字段明细")
    lines.append("")
    if fields:
        lines.append("| 名称 | 源字段 | 类型 | 角色 | 业务定义 | 示例/规则 | 口径状态 | 来源摘要 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for field in fields:
            source_field = _field_source_name(field)
            definition_item = _metric_for_field(field, metric_lookup) or field
            lines.append(
                f"| {_cell(field.get('display_name') or field.get('name'))} | {_code(source_field)} | "
                f"{_code(field.get('type'))} | {_code(field.get('role'))} | {_cell(_definition_text(definition_item))} | "
                f"{_cell(_sample_cell_for_field(field, sample_values))} | {_cell(_definition_status(definition_item))} | "
                f"{_cell(_source_summary_cell(definition_item))} |"
            )
    else:
        lines.append("- 无字段。")
    lines.append("")
    lines.append("### 7.2 指标明细")
    lines.append("")
    if metrics:
        lines.append("| 指标 | 源字段/表达式 | 聚合方式 | 单位 | 业务定义 | 适用粒度 | 口径状态 | 来源摘要 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for metric in metrics:
            source_or_expression = metric.get("expression") or _metric_source_name(metric)
            lines.append(
                f"| {_cell(metric.get('display_name') or metric.get('name'))} | {_code(source_or_expression)} | "
                f"{_code(metric.get('aggregation'))} | {_code(metric.get('unit'))} | {_cell(_definition_text(metric))} | "
                f"{_cell(_short_list(grain))} | {_cell(_definition_status(metric))} | {_cell(_source_summary_cell(metric))} |"
            )
    else:
        lines.append("- 无指标。该数据源按 lookup 维表注册，只提供维度补充，不直接提供业务指标。")
    lines.append("")
    lines.append("### 7.3 筛选器明细")
    lines.append("")
    if filterable_fields:
        lines.append("| 名称 | 类型 | 字段 | 可选值/规则 | 是否必填 | 口径状态 | 来源摘要 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for field in filterable_fields:
            source_field = field.get("source_field") or field.get("physical_name") or field.get("name")
            definition_item = _metric_for_field(field, metric_lookup) or field
            sample_cell = _format_sample_values_with_pattern(_sample_values_for_field(sample_values, source_field))
            lines.append(
                f"| {_cell(field.get('display_name') or field.get('name'))} | DuckDB 筛选字段 | {_code(source_field)} | "
                f"{_cell(sample_cell)} | 否 | {_cell(_definition_status(definition_item))} | {_cell(_source_summary_cell(definition_item))} |"
            )
    else:
        lines.append("- 无已注册筛选候选字段。")
    lines.append("")

    lines.append("## 8. Connector 使用说明")
    lines.append("")
    lines.append("### 8.1 DuckDB 使用说明")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    lines.append(f"| DuckDB 文件 | {_code(duckdb_meta.get('path'))} |")
    lines.append(f"| Schema | {_code(duckdb_meta.get('schema'))} |")
    lines.append(f"| 对象 | {_code(duckdb_meta.get('object_name'))} |")
    lines.append(f"| 对象类型 | {_code(duckdb_meta.get('object_kind'))} |")
    lines.append(f"| 查询边界 | 只读采样；报告不改写业务数据 |")
    lines.append("")
    lines.append("| 业务筛选 | DuckDB 条件示例 | 注意事项 |")
    lines.append("| --- | --- | --- |")
    for field in filterable_fields[:20]:
        source_field = field.get("source_field") or field.get("physical_name") or field.get("name")
        lines.append(f"| {_cell(field.get('display_name') or field.get('name'))} | `{_quote_ident(source_field)} = '<value>'` | 示例写法，正式值以实时数据为准。 |")
    if not filterable_fields:
        lines.append("| 无 | 无 | 无筛选候选字段。 |")
    lines.append("")
    lines.append("### 8.2 Tableau 使用说明")
    lines.append("")
    lines.append("- 无。该报告为 DuckDB 数据源报告。")
    lines.append("")

    lines.append("## 9. 技术维护附录")
    lines.append("")
    lines.append("### 9.1 注册与生成信息")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    rows = [
        ("source_id / dataset_id", dataset_id),
        ("key", dataset_id),
        ("type", _source_type(dataset)),
        ("status", summary.get("status") or "active"),
        ("category", summary.get("category") or business.get("domain")),
        ("mapping_ref", dataset.get("mapping_ref")),
        ("报告生成时间", generated_at.strftime("%Y-%m-%d %H:%M:%S %Z")),
        ("默认报告目录", str(report_dir)),
        ("执行链路", "metadata_yaml -> validate -> generate_report"),
        ("步骤状态", f"register={step_results.get('register', 'success')}, registry=not_written, validate={step_results.get('validate', 'unknown')}"),
    ]
    for key, value in rows:
        lines.append(f"| `{_cell(key)}` | {_code(value)} |")
    lines.append("")
    lines.append("### 9.2 Metadata 来源")
    lines.append("")
    lines.append("| 来源 | 用途 | 状态 |")
    lines.append("| --- | --- | --- |")
    lines.append("| `metadata/datasets/*.yaml` | 数据集、字段、指标、粒度和适用边界 | 已读取 |")
    lines.append(f"| `metadata/mappings/*.yaml` | 源字段到标准语义的映射和 review 状态 | {'已读取' if mapping_rows else '未配置'} |")
    lines.append("| `metadata/dictionaries/*.yaml` | 公共指标、维度和术语定义 | 通过 definition source 间接引用 |")
    lines.append("| `metadata/sources/` | 原始证据、发现结果、用户说明和样本画像 | 作为来源摘要使用，完整路径不进入正文主线 |")
    lines.append("| runtime registry | 运行时可用性 | YAML 模式未反写，不作为业务口径来源 |")
    lines.append("")
    lines.append("### 9.3 映射明细")
    lines.append("")
    if mapping_rows:
        lines.append("| 源字段 | 类型 | 标准 ID | 字段 ID/覆盖 | 维护说明 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in mapping_rows:
            lines.append(f"| {_code(row.get('view_field'))} | {_code(row.get('type'))} | {_code(row.get('standard_id'))} | {_code(row.get('field_id_or_override'))} | {_cell(_mapping_note(row))} |")
    else:
        lines.append("- 待补充映射。")
    lines.append("")
    lines.append("### 9.4 校验结果")
    lines.append("")
    lines.append("| 校验项 | 结果 | 说明 |")
    lines.append("| --- | --- | --- |")
    lines.append(f"| metadata validate | {validate_text} | {'通过，可作为 metadata 说明使用。' if validate_state == 'success' else '未通过或未执行时，需要先修复或补充证据。'} |")
    lines.append("| registry write | skipped | YAML 模式下不反写 runtime registry。 |")
    lines.append("")

    lines.append("## 10. 结论")
    lines.append("")
    lines.append(f"- 这份 DuckDB metadata 当前状态：{ready_status}。")
    lines.append(f"- 可以优先用于：{_short_list(suitable_for)}。")
    lines.append(f"- 暂不应用于：{_short_list(not_suitable_for)}。")
    if review_fields or review_metrics:
        top_reviews = [str(item.get("display_name") or item.get("name")) for item in [*review_metrics, *review_fields]][:5]
        lines.append(f"- 下一步需要确认：{_short_list(top_reviews, limit=5)}。")
    elif pending_questions:
        lines.append(f"- 下一步需要确认：{_short_list(pending_questions, limit=3)}。")
    else:
        lines.append("- 下一步需要确认：无显式待确认项。")
    lines.append("")

    return "\n".join(lines) + "\n"


def write_report(
    *,
    entry: dict[str, Any],
    spec: dict[str, Any],
    report_dir: Path,
    generated_at: datetime,
    sync_mode: str,
    step_results: dict[str, str],
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    filename = build_report_filename(str(entry.get("source_id") or entry.get("key") or "unknown"), generated_at=generated_at)
    report_path = report_dir / filename
    report_path.write_text(
        render_sync_report(
            entry=entry,
            spec=spec,
            generated_at=generated_at,
            report_dir=report_dir,
            sync_mode=sync_mode,
            step_results=step_results,
        ),
        encoding="utf-8",
    )
    return report_path


def write_yaml_report(
    *,
    workspace: Path,
    dataset: dict[str, Any],
    report_dir: Path,
    generated_at: datetime,
    step_results: dict[str, str],
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    dataset_id = str(dataset.get("id") or dataset.get("source_id") or "unknown")
    mapping = _load_dataset_mapping(workspace, dataset)
    filename = build_report_filename(dataset_id, generated_at=generated_at, report_kind="metadata")
    report_path = report_dir / filename
    report_path.write_text(
        render_yaml_metadata_report(
            dataset=dataset,
            mapping=mapping,
            generated_at=generated_at,
            report_dir=report_dir,
            step_results=step_results,
        ),
        encoding="utf-8",
    )
    return report_path


def main() -> None:
    print(
        "[Error] duckdb_report.py is an internal renderer. "
        "Use skills/metadata-report/scripts/generate_report.py --connector duckdb ..."
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
