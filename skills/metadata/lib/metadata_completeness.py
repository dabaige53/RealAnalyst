from __future__ import annotations

from pathlib import Path
from typing import Any

from skills.metadata.lib.metadata_io import iter_mapping_files, load_mapping_file, normalize_dataset


METRIC_LIKE_ROLES = {"metric", "measure", "metric_source", "measure_candidate", "metric_candidate"}
NON_METRIC_ROLES = {"dimension", "filter", "time", "date", "identifier", "id", "attribute"}
NUMERIC_TYPES = {"number", "numeric", "integer", "int", "float", "double", "decimal", "bigint", "smallint"}


def text(value: Any) -> str:
    return str(value or "").strip()


def canonical(value: Any) -> str:
    return text(value).lower()


def is_numeric_type(value: Any) -> bool:
    value_text = canonical(value)
    return value_text in NUMERIC_TYPES or any(token in value_text for token in ("int", "decimal", "double", "numeric"))


def field_aliases(field: dict[str, Any]) -> set[str]:
    aliases = {
        text(field.get("name")),
        text(field.get("display_name")),
        text(field.get("physical_name")),
        text(field.get("source_field")),
    }
    return {item for item in aliases if item}


def metric_aliases(metric: dict[str, Any]) -> set[str]:
    aliases = {
        text(metric.get("name")),
        text(metric.get("display_name")),
        text(metric.get("source_field")),
        text(metric.get("expression")),
    }
    return {item for item in aliases if item}


def is_metric_like_field(field: dict[str, Any]) -> bool:
    role = canonical(field.get("role"))
    if role in METRIC_LIKE_ROLES:
        return True
    if role in NON_METRIC_ROLES:
        return False
    return is_numeric_type(field.get("type")) or is_numeric_type(field.get("duckdb_type"))


def dataset_metric_aliases(dataset: dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    for metric in normalize_dataset(dataset).get("metrics", []):
        if isinstance(metric, dict):
            aliases.update(canonical(item) for item in metric_aliases(metric))
    return {item for item in aliases if item}


def field_has_metric(dataset_metric_names: set[str], field: dict[str, Any]) -> bool:
    return bool({canonical(item) for item in field_aliases(field)} & dataset_metric_names)


def load_dataset_mappings(workspace: Path, dataset_id: str) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    for path in iter_mapping_files(workspace):
        data = load_mapping_file(path)
        if text(data.get("source_id")) == dataset_id:
            mappings.append(data)
    return mappings


def metric_mapping_aliases(item: dict[str, Any]) -> set[str]:
    aliases = {
        text(item.get("view_field")),
        text(item.get("standard_id")),
        text(item.get("field_id_or_override")),
    }
    return {item for item in aliases if item}


def profile_columns(profile: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        ((profile.get("schema") or {}).get("columns") if isinstance(profile.get("schema"), dict) else None),
        profile.get("columns"),
        ((profile.get("probe") or {}).get("columns") if isinstance(profile.get("probe"), dict) else None),
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def completeness_findings(dataset: dict[str, Any], *, mappings: list[dict[str, Any]] | None = None) -> dict[str, list[dict[str, Any]]]:
    normalized = normalize_dataset(dataset)
    metric_names = dataset_metric_aliases(normalized)
    findings: dict[str, list[dict[str, Any]]] = {
        "should_add_metrics": [],
        "needs_review": [],
        "not_metric": [],
        "mapping_gaps": [],
    }

    for field in normalized.get("fields", []):
        if not isinstance(field, dict):
            continue
        if not is_metric_like_field(field):
            continue
        if field_has_metric(metric_names, field):
            continue
        if text(field.get("not_metric_reason")):
            findings["not_metric"].append(
                {
                    "field": text(field.get("name")),
                    "display_name": text(field.get("display_name")) or text(field.get("physical_name")),
                    "reason": text(field.get("not_metric_reason")),
                }
            )
            continue
        findings["should_add_metrics"].append(
            {
                "field": text(field.get("name")),
                "display_name": text(field.get("display_name")) or text(field.get("physical_name")),
                "role": text(field.get("role")),
                "type": text(field.get("type")) or text(field.get("duckdb_type")),
                "reason": "metric-like field is not registered in dataset.metrics",
            }
        )

    for mapping in mappings or []:
        for index, item in enumerate(mapping.get("mappings") or []):
            if not isinstance(item, dict) or item.get("type") != "metric":
                continue
            aliases = {canonical(value) for value in metric_mapping_aliases(item)}
            if aliases & metric_names:
                continue
            findings["mapping_gaps"].append(
                {
                    "mapping_id": text(mapping.get("id")),
                    "index": index,
                    "view_field": text(item.get("view_field")),
                    "standard_id": text(item.get("standard_id")),
                    "reason": "metric mapping has no matching dataset metric",
                }
            )

    for field in normalized.get("fields", []):
        if not isinstance(field, dict) or not isinstance(field.get("sample_profile"), dict):
            continue
        sample = field["sample_profile"]
        sample_source = text(sample.get("source"))
        definition = field.get("business_definition") if isinstance(field.get("business_definition"), dict) else {}
        evidence_sources = {
            text(item.get("source"))
            for item in definition.get("source_evidence", [])
            if isinstance(item, dict)
        }
        if sample_source and sample_source not in evidence_sources:
            findings["needs_review"].append(
                {
                    "field": text(field.get("name")),
                    "display_name": text(field.get("display_name")) or text(field.get("physical_name")),
                    "reason": "sample_profile source is not cited in business_definition.source_evidence",
                    "sample_source": sample_source,
                }
            )
        if (
            canonical(sample.get("observed_type")) == "string"
            and isinstance(sample.get("distinct_count_sample"), int)
            and sample.get("distinct_count_sample") <= 20
            and not field.get("enum_values")
        ):
            findings["needs_review"].append(
                {
                    "field": text(field.get("name")),
                    "display_name": text(field.get("display_name")) or text(field.get("physical_name")),
                    "reason": "low-cardinality sample_profile may need enum_values",
                }
            )

    return findings
