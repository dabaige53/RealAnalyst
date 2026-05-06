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
from report_context import build_report_context, render_markdown, write_context_json  # noqa: E402


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
    return sources


def _evidence_cell(item: dict[str, Any]) -> str:
    sources = _evidence_sources(item)
    return _cell("；".join(sources)) if sources else "未配置"


def _source_label(source: str) -> str:
    return source


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


def _source_summary_cell(item: dict[str, Any]) -> str:
    source_text = _review_source_text(item)
    if source_text == "来源未配置":
        return _definition_source(item)
    return source_text


def _review_location(section: str, item: dict[str, Any], dataset_id: str) -> str:
    name = str(item.get("name") or item.get("display_name") or "").strip()
    selector = f"{section}[name={name}].business_definition.text" if name else f"{section}.business_definition.text"
    return f"metadata/datasets/{dataset_id}.yaml::{selector}"


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
    context = build_report_context(
        connector="duckdb",
        dataset=None,
        mapping=None,
        entry=entry,
        spec=spec,
        source_context=None,
        sample_values=None,
        duckdb_meta=entry.get("duckdb") if isinstance(entry.get("duckdb"), dict) else {},
        export_summary=None,
        manifest=None,
        step_results=step_results,
        generated_at=generated_at,
        report_dir=report_dir,
    )
    return render_markdown(context)


def render_yaml_metadata_report(
    *,
    dataset: dict[str, Any],
    mapping: dict[str, Any] | None,
    generated_at: datetime,
    report_dir: Path,
    step_results: dict[str, str],
) -> str:
    fields_for_sampling = _safe_list_dicts(dataset.get("fields"))
    sample_values = _collect_duckdb_sample_values(dataset, fields_for_sampling)
    context = build_report_context(
        connector="duckdb",
        dataset=dataset,
        mapping=mapping,
        entry=None,
        spec=None,
        source_context=None,
        sample_values=sample_values,
        duckdb_meta=_duckdb_meta(dataset),
        export_summary=None,
        manifest=None,
        step_results=step_results,
        generated_at=generated_at,
        report_dir=report_dir,
    )
    return render_markdown(context)


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
