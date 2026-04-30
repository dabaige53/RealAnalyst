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
    if definition.get("needs_review") is True:
        return f"待确认（置信度 {_display(definition.get('confidence'))}）"
    if definition.get("needs_review") is False:
        return f"已确认（置信度 {_display(definition.get('confidence'))}）"
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

    lines: list[str] = []
    lines.append("# DuckDB Sync Report")
    lines.append("")
    lines.append("## 1. 同步任务概览")
    lines.append("")
    lines.append("- 报告类型：DuckDB 元数据注册/同步明细报告")
    lines.append(f"- 报告生成时间：{generated_at.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    lines.append(f"- 同步对象：`{entry.get('source_id', '')}`")
    lines.append(f"- 显示名称：`{entry.get('display_name', '')}`")
    lines.append(f"- 默认报告目录：`{report_dir}`")
    lines.append("- 本次执行链路：" + " -> ".join(f"`{x}`" for x in ["register", "sync_registry", "validate", "generate_report"]))
    lines.append(f"- 同步模式：`{sync_mode}`")
    lines.append(
        "- 步骤状态："
        + f" register={step_results.get('register', 'unknown')},"
        + f" registry={step_results.get('registry', 'unknown')},"
        + f" validate={step_results.get('validate', 'unknown')}"
    )
    lines.append("")

    lines.append("## 2. 数据源注册信息")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    lines.append(f"| `source_id` | `{entry.get('source_id', '')}` |")
    lines.append(f"| `key` | `{entry.get('key', '')}` |")
    lines.append(f"| `type` | `{entry.get('type', '')}` |")
    lines.append(f"| `status` | `{entry.get('status', '')}` |")
    lines.append(f"| `category` | `{entry.get('category', '')}` |")
    lines.append(f"| `display_name` | `{entry.get('display_name', '')}` |")
    lines.append(f"| `description` | `{entry.get('description', '')}` |")
    lines.append(f"| `db_path` | `{duckdb_meta.get('db_path', '')}` |")
    lines.append(f"| `schema` | `{duckdb_meta.get('schema', '')}` |")
    lines.append(f"| `object_name` | `{duckdb_meta.get('object_name', '')}` |")
    lines.append(f"| `object_kind` | `{duckdb_meta.get('object_kind', '')}` |")
    lines.append("")

    lines.append("## 3. 本次写入摘要")
    lines.append("")
    lines.append(f"- 字段总数：`{len(_safe_list_str(entry.get('fields')))}`")
    lines.append(f"- 维度数：`{len(dimensions)}`")
    lines.append(f"- 指标数：`{len(measures)}`")
    lines.append(f"- 筛选器数：`{len(filters)}`")
    lines.append(f"- 粒度字段数：`{len(_safe_list_str(semantics.get('grain')))}`")
    lines.append(f"- 时间字段数：`{len(_safe_list_str(semantics.get('time_fields')))}`")
    lines.append("")

    lines.append("## 4. 语义层明细")
    lines.append("")
    lines.append("### 4.1 粒度")
    lines.append("")
    for item in _safe_list_str(semantics.get("grain")) or ["未配置"]:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("### 4.2 时间字段")
    lines.append("")
    for item in _safe_list_str(semantics.get("time_fields")) or ["未配置"]:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("### 4.3 适用场景")
    lines.append("")
    for item in _safe_list_str(semantics.get("suitable_for")) or ["未配置"]:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("### 4.4 不适用场景")
    lines.append("")
    for item in _safe_list_str(semantics.get("not_suitable_for")) or ["未配置"]:
        lines.append(f"- `{item}`")
    lines.append("")

    lines.append("## 5. 字段明细")
    lines.append("")
    lines.append("### 5.1 维度")
    lines.append("")
    if dimensions:
        lines.append("| 字段 | 类型 |")
        lines.append("| --- | --- |")
        for item in dimensions:
            lines.append(f"| `{item.get('name', '')}` | `{item.get('data_type', '')}` |")
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("### 5.2 指标")
    lines.append("")
    if measures:
        lines.append("| 字段 | 类型 |")
        lines.append("| --- | --- |")
        for item in measures:
            lines.append(f"| `{item.get('name', '')}` | `{item.get('data_type', '')}` |")
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("### 5.3 筛选器")
    lines.append("")
    if filters:
        lines.append("| 字段 | 显示名 | 应用方式 |")
        lines.append("| --- | --- | --- |")
        for item in filters:
            lines.append(f"| `{item.get('key', '')}` | `{item.get('display_name', '')}` | `{item.get('apply_via', '')}` |")
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("## 6. 校验结果")
    lines.append("")
    if step_results.get("validate") == "success":
        lines.append("- 本次注册校验通过，可供后续 `data-export` 使用。")
    elif step_results.get("validate") == "failed":
        lines.append("- 本次注册已落库，但校验失败，需要先修正 registry/spec 后再用于正式导出。")
    else:
        lines.append("- 本次未执行正式校验。")
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

    lines: list[str] = []
    lines.append(f"# {_display(dataset.get('display_name'))} 注册报告")
    lines.append("")
    lines.append("## 1. 同步任务概览")
    lines.append("")
    lines.append("- 报告类型：DuckDB 元数据注册/同步明细报告")
    lines.append(f"- 报告生成时间：{generated_at.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    lines.append(f"- 同步对象：`{dataset_id}`")
    lines.append(f"- 显示名称：`{_cell(dataset.get('display_name'))}`")
    lines.append(f"- 默认报告目录：`{report_dir}`")
    lines.append("- 本次执行链路：`metadata_yaml` -> `validate` -> `generate_report`")
    lines.append("- 同步模式：`metadata-yaml`")
    lines.append(
        "- 步骤状态："
        + f"register={step_results.get('register', 'success')},"
        + " registry=not_written,"
        + f" validate={step_results.get('validate', 'unknown')}"
    )
    lines.append("")

    lines.append("## 2. 数据源注册信息")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    rows = [
        ("source_id", dataset_id),
        ("key", dataset_id),
        ("type", _source_type(dataset)),
        ("status", summary.get("status") or "active"),
        ("category", summary.get("category") or business.get("domain")),
        ("display_name", dataset.get("display_name")),
        ("description", dataset.get("description") or business.get("description")),
        ("db_path", duckdb_meta.get("path")),
        ("schema", duckdb_meta.get("schema")),
        ("object_name", duckdb_meta.get("object_name")),
        ("object_kind", duckdb_meta.get("object_kind")),
        ("row_count", duckdb_meta.get("row_count")),
        ("column_count", duckdb_meta.get("column_count") or len(fields)),
        ("mapping_ref", dataset.get("mapping_ref")),
    ]
    for key, value in rows:
        lines.append(f"| `{key}` | {_code(value)} |")
    lines.append("")

    lines.append("## 3. 本次写入摘要")
    lines.append("")
    lines.append(f"- 字段总数：`{len(fields)}`")
    lines.append(f"- 维度数：`{dimensions}`")
    lines.append(f"- 指标数：`{len(metrics)}`")
    lines.append(f"- 可作为 `sql_where` 候选筛选字段数：`{filters}`")
    lines.append(f"- 粒度字段数：`{len(_safe_list_str(business.get('grain')))}`")
    lines.append(f"- 时间字段数：`{len(_safe_list_str(business.get('time_fields')))}`")
    lines.append(f"- 示例值采样字段数：`{_sampled_field_count(sample_values)}`")
    lines.append(f"- mapping 条目数：`{len(mapping_rows)}`")
    lines.append("")

    lines.append("## 4. 语义层明细")
    lines.append("")
    lines.append("### 4.1 粒度")
    lines.append("")
    for item in _safe_list_str(business.get("grain")) or ["未配置"]:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("### 4.2 时间字段")
    lines.append("")
    for item in _safe_list_str(business.get("time_fields")) or ["未配置"]:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("### 4.3 适用场景")
    lines.append("")
    for item in _safe_list_str(business.get("suitable_for")) or ["未配置"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### 4.4 不适用场景")
    lines.append("")
    for item in _safe_list_str(business.get("not_suitable_for")) or ["未配置"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 5. 字段明细")
    lines.append("")
    if fields:
        lines.append("| 展示名 | 源字段 | DuckDB 类型 | metadata 类型 | 角色 | 业务定义 | 定义来源 | 示例/规则 | 证据 | Review |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for field in fields:
            source_field = _field_source_name(field)
            definition_item = _metric_for_field(field, metric_lookup) or field
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(field.get("display_name") or field.get("name")),
                        _code(source_field),
                        _code(field.get("duckdb_type") or field.get("data_type") or field.get("type")),
                        _code(field.get("type")),
                        _code(field.get("role")),
                        _cell(_definition_text(definition_item)),
                        _code(_definition_source(definition_item)),
                        _cell(_sample_cell_for_field(field, sample_values)),
                        _evidence_cell(definition_item),
                        _cell(_review_text(definition_item)),
                    ]
                )
                + " |"
            )
    else:
        lines.append("- 无字段。")
    lines.append("")

    lines.append("## 6. 指标明细")
    lines.append("")
    if metrics:
        lines.append("| 指标 | 源字段 | 表达式 | 聚合方式 | 单位 | 业务定义 | 定义来源 | 证据 | Review |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for metric in metrics:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(metric.get("display_name") or metric.get("name")),
                        _code(_metric_source_name(metric)),
                        _code(metric.get("expression")),
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
    else:
        lines.append("- 无指标。该数据源按 lookup 维表注册，只提供维度补充，不直接提供业务指标。")
    lines.append("")

    lines.append("## 7. 筛选器明细")
    lines.append("")
    lines.append("DuckDB 数据源没有 Tableau 参数；后续取数筛选应通过 `sql_where` 或 data-export 的 DuckDB 筛选参数表达。")
    lines.append("")
    lines.append("> 示例值为报告生成时从 DuckDB 当前对象中只读抽取的非空样本，不代表完整枚举清单；正式筛选仍以实时数据和业务口径为准。")
    lines.append("")
    filterable_fields = [field for field in fields if field.get("role") in {"dimension", "time_dimension"}]
    if filterable_fields:
        lines.append("| 字段 | 显示名 | 应用方式 | 可选值/示例/规则 | 说明 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for field in filterable_fields:
            source_field = field.get("source_field") or field.get("physical_name") or field.get("name")
            sample_cell = _cell(_format_sample_values_with_pattern(_sample_values_for_field(sample_values, source_field)))
            lines.append(f"| {_code(source_field)} | {_cell(field.get('display_name') or field.get('name'))} | `sql_where` | {sample_cell} | 按 {_code(source_field)} 过滤；示例值来自 DuckDB 当前非空样本，正式取数仍以实时数据为准。 |")
    else:
        lines.append("- 无已注册筛选候选字段。")
    lines.append("")

    lines.append("## 8. 映射与 Review 问题")
    lines.append("")
    lines.append("### 8.1 已注册映射")
    lines.append("")
    if mapping_rows:
        lines.append("| 源字段 | 类型 | 标准 ID | 字段 ID/覆盖 | 说明 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in mapping_rows:
            lines.append(f"| {_code(row.get('view_field'))} | {_code(row.get('type'))} | {_code(row.get('standard_id'))} | {_code(row.get('field_id_or_override'))} | {_cell(_mapping_note(row))} |")
    else:
        lines.append("- 待补充映射。")
    lines.append("")
    lines.append("### 8.2 待确认问题")
    lines.append("")
    pending_questions = _pending_questions(maintenance.get("pending_questions"))
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
    lines.append("")

    lines.append("## 9. 校验结果")
    lines.append("")
    if step_results.get("validate") == "success":
        lines.append("- `metadata validate`：通过。")
    elif step_results.get("validate") == "failed":
        lines.append("- `metadata validate`：失败；本报告仅可作为待修复清单。")
    else:
        lines.append("- `metadata validate`：未执行。")
    lines.append("- 本报告基于 metadata YAML、mapping YAML 和 source evidence，不把 `registry.db` 当作业务口径来源。")
    lines.append("")

    lines.append("## 10. 本条数据源的结论")
    lines.append("")
    if metrics:
        lines.append(f"- `{dataset_id}` 已按 DuckDB 可分析数据源注册，字段、指标、粒度和时间字段已进入 metadata。")
    else:
        lines.append(f"- `{dataset_id}` 已按 DuckDB lookup 维表注册，适合作为维度补充表，不直接作为经营事实表或指标来源。")
    lines.append("- 后续分析前应优先通过 metadata context 拉取最小语义上下文；带 `待确认` 标记的字段或指标不能直接当作最终确定口径。")
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
