#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _business_definition(item: dict[str, Any]) -> dict[str, Any]:
    definition = item.get("business_definition")
    if not isinstance(definition, dict):
        return {"text": "", "confidence": None, "needs_review": False}
    return {
        "text": _as_text(definition.get("text")),
        "confidence": definition.get("confidence"),
        "needs_review": bool(definition.get("needs_review")),
    }


def _selected_items(items: list[Any], names: list[str] | None) -> list[dict[str, Any]]:
    selected = {name for name in names or []}
    records = [item for item in items if isinstance(item, dict)]
    if names is None:
        return records
    return [item for item in records if _as_text(item.get("name")) in selected]


def _missing_names(items: list[dict[str, Any]], names: list[str] | None) -> list[str]:
    if names is None:
        return []
    available = {_as_text(item.get("name")) for item in items}
    return [name for name in names if name not in available]


def _field_pack(field: dict[str, Any]) -> dict[str, Any]:
    definition = _business_definition(field)
    return {
        "name": _as_text(field.get("name")),
        "role": _as_text(field.get("role")),
        "type": _as_text(field.get("type")),
        "description": _as_text(field.get("description")),
        "definition": definition["text"],
        "confidence": definition["confidence"],
        "needs_review": definition["needs_review"],
    }


def _metric_pack(metric: dict[str, Any]) -> dict[str, Any]:
    definition = _business_definition(metric)
    return {
        "name": _as_text(metric.get("name")),
        "expression": _as_text(metric.get("expression")),
        "unit": _as_text(metric.get("unit")),
        "description": _as_text(metric.get("description")),
        "definition": definition["text"],
        "confidence": definition["confidence"],
        "needs_review": definition["needs_review"],
    }


def build_context_pack(
    dataset: dict[str, Any],
    *,
    metrics: list[str] | None = None,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    business = dataset.get("business") if isinstance(dataset.get("business"), dict) else {}
    maintenance = dataset.get("maintenance") if isinstance(dataset.get("maintenance"), dict) else {}
    source = dataset.get("source") if isinstance(dataset.get("source"), dict) else {}

    field_items = [field for field in _as_list(dataset.get("fields")) if isinstance(field, dict)]
    metric_items = [metric for metric in _as_list(dataset.get("metrics")) if isinstance(metric, dict)]
    field_packs = [_field_pack(field) for field in _selected_items(field_items, fields)]
    metric_packs = [_metric_pack(metric) for metric in _selected_items(metric_items, metrics)]

    return {
        "dataset": {
            "id": _as_text(dataset.get("id") or dataset.get("source_id")),
            "display_name": _as_text(dataset.get("display_name")),
            "description": _as_text(dataset.get("description") or business.get("description")),
            "domain": _as_text(business.get("domain")),
            "source_connector": _as_text(source.get("connector")),
            "source_object": _as_text(source.get("object")),
        },
        "grain": _as_list(business.get("grain")),
        "time_fields": _as_list(business.get("time_fields")),
        "suitable_for": _as_list(business.get("suitable_for")),
        "not_suitable_for": _as_list(business.get("not_suitable_for")),
        "fields": field_packs,
        "metrics": metric_packs,
        "missing_fields": _missing_names(field_items, fields),
        "missing_metrics": _missing_names(metric_items, metrics),
        "pending_questions": _as_list(maintenance.get("pending_questions")),
        "review_required": any(item["needs_review"] for item in [*field_packs, *metric_packs]),
    }
