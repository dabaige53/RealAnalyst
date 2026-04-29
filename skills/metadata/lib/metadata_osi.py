from __future__ import annotations

from typing import Any


def _as_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dataset_name(dataset: dict[str, Any]) -> str:
    source = dataset.get("source", {}) if isinstance(dataset.get("source"), dict) else {}
    object_name = _as_text(source.get("object"))
    duckdb = source.get("duckdb", {}) if isinstance(source.get("duckdb"), dict) else {}
    if _as_text(duckdb.get("object_name")):
        return _as_text(duckdb.get("object_name"))
    if object_name:
        return object_name.split(".")[-1]
    source_id = _as_text(dataset.get("source_id") or dataset.get("id"))
    return source_id.split(".")[-1] if source_id else "dataset"


def _field_review_required(field: dict[str, Any]) -> bool:
    definition = field.get("business_definition")
    return bool(definition.get("needs_review")) if isinstance(definition, dict) else False


def _metric_review_required(metric: dict[str, Any]) -> bool:
    definition = metric.get("business_definition")
    return bool(definition.get("needs_review")) if isinstance(definition, dict) else False


def _map_dimension(field: dict[str, Any]) -> dict[str, Any]:
    dimension = {
        "name": _as_text(field.get("name")),
        "label": _as_text(field.get("display_name") or field.get("name")),
        "description": _as_text(field.get("description")),
        "type": _as_text(field.get("type")),
    }
    return {key: value for key, value in dimension.items() if value != ""}


def _map_measure(field: dict[str, Any]) -> dict[str, Any]:
    measure = {
        "name": _as_text(field.get("name")),
        "label": _as_text(field.get("display_name") or field.get("name")),
        "description": _as_text(field.get("description")),
        "expression": _as_text(field.get("physical_name") or field.get("name")),
        "type": _as_text(field.get("type")),
    }
    return {key: value for key, value in measure.items() if value != ""}


def _map_metric(metric: dict[str, Any], *, dataset_name: str) -> dict[str, Any]:
    payload = {
        "name": _as_text(metric.get("name")),
        "label": _as_text(metric.get("display_name") or metric.get("name")),
        "description": _as_text(metric.get("description")),
        "expression": _as_text(metric.get("expression")),
        "dataset": dataset_name,
    }
    return {key: value for key, value in payload.items() if value != ""}


def _review_payload(item: dict[str, Any]) -> dict[str, Any]:
    definition = item.get("business_definition") if isinstance(item.get("business_definition"), dict) else {}
    payload = {
        "name": _as_text(item.get("name")),
        "label": _as_text(item.get("display_name") or item.get("name")),
        "needs_review": bool(definition.get("needs_review")),
        "confidence": definition.get("confidence"),
        "text": _as_text(definition.get("text")),
    }
    return {
        key: value
        for key, value in payload.items()
        if value not in ("", None)
    }


def _map_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    fields = [field for field in _as_list(dataset.get("fields")) if isinstance(field, dict)]
    dimensions = [_map_dimension(field) for field in fields if _as_text(field.get("role")) != "metric_source"]
    measures = [_map_measure(field) for field in fields if _as_text(field.get("role")) == "metric_source"]

    payload = {
        "name": _dataset_name(dataset),
        "label": _as_text(dataset.get("display_name")),
        "description": _as_text(dataset.get("description") or dataset.get("business", {}).get("description")),
        "dimensions": [item for item in dimensions if item.get("name")],
        "measures": [item for item in measures if item.get("name")],
    }
    return payload


def _dataset_extension(dataset: dict[str, Any]) -> dict[str, Any]:
    fields = [field for field in _as_list(dataset.get("fields")) if isinstance(field, dict)]
    metrics = [metric for metric in _as_list(dataset.get("metrics")) if isinstance(metric, dict)]
    maintenance = dataset.get("maintenance", {}) if isinstance(dataset.get("maintenance"), dict) else {}
    review_fields = [_review_payload(field) for field in fields if _field_review_required(field)]
    review_metrics = [_review_payload(metric) for metric in metrics if _metric_review_required(metric)]
    return {
        "dataset_name": _dataset_name(dataset),
        "source_id": _as_text(dataset.get("source_id") or dataset.get("id")),
        "maintenance": {
            "managed_by": maintenance.get("managed_by"),
            "status": maintenance.get("status"),
            "pending_questions": _as_list(maintenance.get("pending_questions")),
        },
        "review_fields": review_fields,
        "review_metrics": review_metrics,
        "needs_review": bool(review_fields or review_metrics),
    }


def build_osi_model(model_name: str, datasets: list[dict[str, Any]]) -> dict[str, Any]:
    mapped_datasets = [_map_dataset(dataset) for dataset in datasets]
    mapped_metrics = [
        _map_metric(metric, dataset_name=_dataset_name(dataset))
        for dataset in datasets
        for metric in _as_list(dataset.get("metrics"))
        if isinstance(metric, dict) and _as_text(metric.get("name"))
    ]
    extension = {
        "vendor_name": "COMMON",
        "name": "realanalyst_review_metadata",
        "extension": {
            "model_name": model_name,
            "datasets": [_dataset_extension(dataset) for dataset in datasets],
        },
    }
    return {
        "version": "0.1.1",
        "semantic_model": [
            {
                "name": model_name,
                "datasets": mapped_datasets,
                "metrics": mapped_metrics,
                "custom_extensions": [extension],
            }
        ],
    }
