#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from runtime.tableau.sqlite_store import db_path, legacy_db_path, save_entry, save_spec  # noqa: E402
from skills.metadata.lib.metadata_io import (  # noqa: E402
    MetadataError,
    iter_dataset_files,
    load_dataset_file,
    normalize_dataset,
    resolve_dataset_path,
)
from skills.metadata.scripts.validate_metadata import validate_dataset  # noqa: E402


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _field_source_name(field: dict[str, Any]) -> str:
    for key in ("source_field", "physical_name", "display_name", "name"):
        value = _safe_str(field.get(key))
        if value:
            return value
    return ""


def _field_display_name(field: dict[str, Any]) -> str:
    return _safe_str(field.get("display_name")) or _field_source_name(field)


def _metric_name(metric: dict[str, Any]) -> str:
    return _safe_str(metric.get("name")) or _safe_str(metric.get("display_name"))


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _has_review_flag(items: list[Any]) -> bool:
    for item in items:
        if not isinstance(item, dict):
            continue
        definition = item.get("business_definition")
        if isinstance(definition, dict) and definition.get("needs_review") is True:
            return True
    return False


def _field_data_type(field: dict[str, Any]) -> str:
    field_type = _safe_str(field.get("type")).lower()
    if field_type in {"number", "integer", "float", "double", "decimal"}:
        return "number"
    if field_type in {"date", "datetime", "time", "timestamp"}:
        return field_type
    return "string"


def _is_measure_field(field: dict[str, Any]) -> bool:
    role = _safe_str(field.get("role")).lower()
    return role in {"metric_source", "measure", "measure_candidate"}


def _is_filter_field(field: dict[str, Any]) -> bool:
    role = _safe_str(field.get("role")).lower()
    return role in {"dimension", "time_dimension", "identifier", "category"}


def _connector_type(connector: str, source: dict[str, Any]) -> str:
    if connector == "duckdb":
        object_kind = _safe_str((source.get("duckdb") or {}).get("object_kind")).lower()
        return "duckdb_view" if object_kind == "view" else "duckdb_table"
    if connector == "tableau":
        return "view"
    if connector in {"csv", "excel", "file"}:
        return f"{connector}_dataset"
    return "dataset"


def _connector_payload(source: dict[str, Any], connector: str) -> dict[str, Any]:
    payload = source.get(connector)
    if isinstance(payload, dict):
        out = dict(payload)
    else:
        out = {}

    if connector == "duckdb":
        if "path" in out and "db_path" not in out:
            out["db_path"] = out.pop("path")
        out.setdefault("object_name", _safe_str(source.get("object")).split(".")[-1])
        out.setdefault("schema", "main")
    return out


def build_entry_and_spec(dataset: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    dataset = normalize_dataset(dataset)
    dataset_id = _safe_str(dataset.get("id"))
    source = dataset.get("source") if isinstance(dataset.get("source"), dict) else {}
    business = dataset.get("business") if isinstance(dataset.get("business"), dict) else {}
    fields = [x for x in _safe_list(dataset.get("fields")) if isinstance(x, dict)]
    metrics = [x for x in _safe_list(dataset.get("metrics")) if isinstance(x, dict)]
    connector = _safe_str(source.get("connector")) or "unknown"

    field_names = [_field_source_name(field) for field in fields]
    field_names = [name for name in field_names if name]
    dimension_names = [_field_source_name(field) for field in fields if _is_filter_field(field)]
    dimension_names = [name for name in dimension_names if name]
    measure_fields = [_field_source_name(field) for field in fields if _is_measure_field(field)]
    measure_fields = [name for name in measure_fields if name]
    metric_names = [_metric_name(metric) for metric in metrics]
    available_metric_names = _dedupe([name for name in [*measure_fields, *metric_names] if name])
    review_required = _has_review_flag(fields) or _has_review_flag(metrics)

    entry: dict[str, Any] = {
        "key": dataset_id,
        "source_id": dataset_id,
        "type": _connector_type(connector, source),
        "source_backend": connector,
        "display_name": dataset.get("display_name") or dataset_id,
        "description": dataset.get("description") or business.get("description") or "",
        "status": "active",
        "category": business.get("domain") or "dataset",
        "tags": [connector, business.get("domain") or "dataset"],
        "fields": field_names,
        "semantics": {
            "grain": _safe_list(business.get("grain")),
            "primary_dimensions": dimension_names,
            "available_metrics": available_metric_names,
            "time_fields": _safe_list(business.get("time_fields")),
            "suitable_for": _safe_list(business.get("suitable_for")),
            "not_suitable_for": _safe_list(business.get("not_suitable_for")),
            "review_required": review_required,
        },
        "agent": {
            "default_template": "executive_onepage",
            "suggested_questions": _safe_list(business.get("sample_questions"))[:3],
            "require_verifier": True,
        },
        "metadata": {
            "dataset_id": dataset_id,
            "mapping_ref": dataset.get("mapping_ref"),
            "dictionary_refs": _safe_list(dataset.get("dictionary_refs")),
        },
    }
    connector_data = _connector_payload(source, connector)
    if connector_data:
        entry[connector] = connector_data

    limitations = list(_safe_list(business.get("not_suitable_for")))
    if review_required:
        limitations.append("Some fields or metrics have needs_review=true in metadata YAML.")

    spec = {
        "entry_key": dataset_id,
        "display_name": dataset.get("display_name") or dataset_id,
        "updated": datetime.now(timezone.utc).astimezone().isoformat(),
        "source_backend": connector,
        "fields": field_names,
        "grain": _safe_list(business.get("grain")),
        "time_fields": _safe_list(business.get("time_fields")),
        "dimensions": [
            {"name": _field_source_name(field), "display_name": _field_display_name(field), "data_type": _field_data_type(field)}
            for field in fields
            if _is_filter_field(field) and _field_source_name(field)
        ],
        "measures": [
            {"name": name, "display_name": name, "data_type": "number"}
            for name in measure_fields
        ],
        "metrics": [
            {
                "name": _metric_name(metric),
                "display_name": _safe_str(metric.get("display_name")) or _metric_name(metric),
                "expression": _safe_str(metric.get("expression")),
                "source_field": _safe_str(metric.get("source_field")),
                "description": _safe_str(metric.get("description")),
                "unit": _safe_str(metric.get("unit")),
                "aggregation": _safe_str(metric.get("aggregation")),
            }
            for metric in metrics
            if _metric_name(metric)
        ],
        "filters": [
            {"key": _field_source_name(field), "display_name": _field_display_name(field), "apply_via": "sql_where"}
            for field in fields
            if _is_filter_field(field) and _field_source_name(field)
        ],
        "recommended_questions": _safe_list(business.get("sample_questions")),
        "limitations": limitations,
        "review_required": review_required,
        "metadata_dataset_id": dataset_id,
    }
    if connector_data:
        spec.update(connector_data)
    return entry, spec


def _dataset_paths(workspace: Path, dataset_id: str | None, all_datasets: bool) -> list[Path]:
    if all_datasets:
        return list(iter_dataset_files(workspace))
    if dataset_id:
        return [resolve_dataset_path(workspace, dataset_id)]
    raise MetadataError("Specify --dataset-id or --all")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync validated metadata dataset YAML into runtime/registry.db.")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--dataset-id")
    scope.add_argument("--all", action="store_true")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    results: list[dict[str, Any]] = []
    for path in _dataset_paths(workspace, args.dataset_id, args.all):
        raw = load_dataset_file(path)
        errors = validate_dataset(raw, path=path)
        if errors:
            results.append({"dataset_id": raw.get("id"), "status": "invalid", "errors": errors})
            continue
        entry, spec = build_entry_and_spec(raw)
        if not args.dry_run:
            save_entry(entry)
            save_spec(spec)
        results.append(
            {
                "dataset_id": entry["source_id"],
                "status": "preview" if args.dry_run else "synced",
                "entry_key": entry["key"],
                "field_count": len(entry.get("fields") or []),
                "dimension_count": len(spec.get("dimensions") or []),
                "measure_count": len(spec.get("measures") or []),
                "review_required": spec.get("review_required"),
            }
        )

    success = all(item.get("status") in {"preview", "synced"} for item in results)
    print(
        json.dumps(
            {
                "success": success,
                "dry_run": args.dry_run,
                "registry_db": str(db_path()),
                "legacy_registry_db": str(legacy_db_path()),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
