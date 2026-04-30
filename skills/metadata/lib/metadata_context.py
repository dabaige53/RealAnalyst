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
        "source_type": _as_text(definition.get("source_type")),
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


def _ref_ids(values: Any) -> set[str]:
    refs: set[str] = set()
    for value in _as_list(values):
        if isinstance(value, str):
            refs.add(_as_text(value))
        elif isinstance(value, dict):
            refs.add(_as_text(value.get("id") or value.get("dictionary_id") or value.get("mapping_id")))
    return {ref for ref in refs if ref}


def _dictionary_id(dictionary: dict[str, Any]) -> str:
    return _as_text(dictionary.get("id") or dictionary.get("dictionary_id"))


def _mapping_id(mapping: dict[str, Any]) -> str:
    return _as_text(mapping.get("id") or mapping.get("mapping_id"))


def _field_pack(field: dict[str, Any], *, source_layer: str, dictionary_id: str = "") -> dict[str, Any]:
    definition = _business_definition(field)
    payload = {
        "name": _as_text(field.get("name")),
        "role": _as_text(field.get("role")),
        "type": _as_text(field.get("type")),
        "description": _as_text(field.get("description")),
        "definition": definition["text"],
        "definition_source": definition["source_type"],
        "confidence": definition["confidence"],
        "needs_review": definition["needs_review"],
        "source_layer": source_layer,
        "dictionary_id": dictionary_id,
    }
    return {key: value for key, value in payload.items() if value != ""}


def _metric_pack(metric: dict[str, Any], *, source_layer: str, dictionary_id: str = "") -> dict[str, Any]:
    definition = _business_definition(metric)
    payload = {
        "name": _as_text(metric.get("name")),
        "expression": _as_text(metric.get("expression")),
        "aggregation": _as_text(metric.get("aggregation")),
        "unit": _as_text(metric.get("unit")),
        "description": _as_text(metric.get("description")),
        "definition": definition["text"],
        "definition_source": definition["source_type"],
        "confidence": definition["confidence"],
        "needs_review": definition["needs_review"],
        "source_layer": source_layer,
        "dictionary_id": dictionary_id,
    }
    return {key: value for key, value in payload.items() if value != ""}


def _glossary_pack(item: dict[str, Any], *, dictionary_id: str) -> dict[str, Any]:
    definition = _business_definition(item)
    payload = {
        "section": _as_text(item.get("section")),
        "key": _as_text(item.get("key") or item.get("item_key")),
        "display_name": _as_text(item.get("display_name")),
        "english_name": _as_text(item.get("english_name")),
        "definition": _as_text(item.get("definition")),
        "business_definition": definition["text"],
        "confidence": definition["confidence"],
        "needs_review": definition["needs_review"],
        "synonyms": _as_list(item.get("synonyms")),
        "values": _as_list(item.get("values")),
        "dictionary_id": dictionary_id,
    }
    return {key: value for key, value in payload.items() if value not in ("", [])}


def _mapping_pack(mapping: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    return {
        "mapping_id": _mapping_id(mapping),
        "source_id": _as_text(mapping.get("source_id")),
        "type": _as_text(item.get("type")),
        "view_field": _as_text(item.get("view_field")),
        "standard_id": _as_text(item.get("standard_id")),
        "field_id_or_override": _as_text(item.get("field_id_or_override")),
        "definition_override": _as_text(item.get("definition_override")),
        "notes": _as_text(item.get("notes")),
    }


def _referenced_dictionaries(dataset: dict[str, Any], dictionaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs = _ref_ids(dataset.get("dictionary_refs"))
    if not refs:
        return []
    return [dictionary for dictionary in dictionaries if _dictionary_id(dictionary) in refs]


def _referenced_mappings(dataset: dict[str, Any], mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dataset_id = _as_text(dataset.get("id"))
    refs = _ref_ids(dataset.get("mapping_ref"))
    matched = [mapping for mapping in mappings if _mapping_id(mapping) in refs]
    if matched:
        return matched
    return [mapping for mapping in mappings if _as_text(mapping.get("source_id")) == dataset_id]


def build_context_pack(
    dataset: dict[str, Any],
    *,
    metrics: list[str] | None = None,
    fields: list[str] | None = None,
    dictionaries: list[dict[str, Any]] | None = None,
    mappings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    business = dataset.get("business") if isinstance(dataset.get("business"), dict) else {}
    maintenance = dataset.get("maintenance") if isinstance(dataset.get("maintenance"), dict) else {}
    source = dataset.get("source") if isinstance(dataset.get("source"), dict) else {}

    referenced_dictionaries = _referenced_dictionaries(dataset, dictionaries or [])
    referenced_mappings = _referenced_mappings(dataset, mappings or [])
    all_mapping_items = [
        _mapping_pack(mapping, item)
        for mapping in referenced_mappings
        for item in _as_list(mapping.get("mappings"))
        if isinstance(item, dict)
    ]

    field_items = [field for field in _as_list(dataset.get("fields")) if isinstance(field, dict)]
    metric_items = [metric for metric in _as_list(dataset.get("metrics")) if isinstance(metric, dict)]
    dictionary_fields = [
        (field, _dictionary_id(dictionary))
        for dictionary in referenced_dictionaries
        for field in _as_list(dictionary.get("fields"))
        if isinstance(field, dict)
    ]
    dictionary_metrics = [
        (metric, _dictionary_id(dictionary))
        for dictionary in referenced_dictionaries
        for metric in _as_list(dictionary.get("metrics"))
        if isinstance(metric, dict)
    ]
    glossary_items = [
        _glossary_pack(item, dictionary_id=_dictionary_id(dictionary))
        for dictionary in referenced_dictionaries
        for item in _as_list(dictionary.get("glossary"))
        if isinstance(item, dict)
    ]

    selected_metric_names = set(metrics or [])
    selected_field_names = set(fields or [])
    if selected_metric_names or selected_field_names:
        selected_names = selected_metric_names | selected_field_names
        mapping_items = [
            item
            for item in all_mapping_items
            if item.get("standard_id") in selected_names
            or item.get("view_field") in selected_names
            or item.get("field_id_or_override") in selected_names
        ]
    else:
        mapping_items = all_mapping_items

    mapped_metric_names = {item["standard_id"] for item in mapping_items if item.get("type") == "metric" and item.get("standard_id")}
    effective_metric_names = selected_metric_names or None
    if selected_metric_names:
        effective_metric_names = selected_metric_names | mapped_metric_names

    mapped_field_names = {
        item["standard_id"]
        for item in mapping_items
        if item.get("type") in {"field", "dimension"} and item.get("standard_id")
    }
    effective_field_names = selected_field_names or None
    if selected_field_names:
        effective_field_names = selected_field_names | mapped_field_names

    selected_dataset_fields = _selected_items(field_items, fields)
    selected_dataset_metrics = _selected_items(metric_items, metrics)
    selected_dictionary_fields = [
        (field, dictionary_id)
        for field, dictionary_id in dictionary_fields
        if effective_field_names is None or _as_text(field.get("name")) in effective_field_names
    ]
    selected_dictionary_metrics = [
        (metric, dictionary_id)
        for metric, dictionary_id in dictionary_metrics
        if effective_metric_names is None or _as_text(metric.get("name")) in effective_metric_names
    ]

    field_packs = [_field_pack(field, source_layer="dataset") for field in selected_dataset_fields]
    field_packs.extend(_field_pack(field, source_layer="dictionary", dictionary_id=dictionary_id) for field, dictionary_id in selected_dictionary_fields)
    metric_packs = [_metric_pack(metric, source_layer="dataset") for metric in selected_dataset_metrics]
    metric_packs.extend(_metric_pack(metric, source_layer="dictionary", dictionary_id=dictionary_id) for metric, dictionary_id in selected_dictionary_metrics)

    available_fields = [*field_items, *(field for field, _ in dictionary_fields), *({"name": item.get("standard_id")} for item in all_mapping_items)]
    available_metrics = [*metric_items, *(metric for metric, _ in dictionary_metrics), *({"name": item.get("standard_id")} for item in all_mapping_items)]

    return {
        "dataset": {
            "id": _as_text(dataset.get("id")),
            "display_name": _as_text(dataset.get("display_name")),
            "description": _as_text(dataset.get("description") or business.get("description")),
            "domain": _as_text(business.get("domain")),
            "source_connector": _as_text(source.get("connector")),
            "source_object": _as_text(source.get("object")),
            "runtime_source_id": _as_text(source.get("source_id") or dataset.get("id")),
        },
        "dictionary_refs": [_dictionary_id(dictionary) for dictionary in referenced_dictionaries],
        "mapping_refs": [_mapping_id(mapping) for mapping in referenced_mappings],
        "grain": _as_list(business.get("grain")),
        "time_fields": _as_list(business.get("time_fields")),
        "suitable_for": _as_list(business.get("suitable_for")),
        "not_suitable_for": _as_list(business.get("not_suitable_for")),
        "fields": field_packs,
        "metrics": metric_packs,
        "mappings": mapping_items,
        "glossary": glossary_items,
        "missing_fields": _missing_names(available_fields, fields),
        "missing_metrics": _missing_names(available_metrics, metrics),
        "pending_questions": _as_list(maintenance.get("pending_questions")),
        "review_required": any(item["needs_review"] for item in [*field_packs, *metric_packs, *glossary_items]),
    }


def build_multi_context_pack(
    datasets: list[dict[str, Any]],
    *,
    metrics: list[str] | None = None,
    fields: list[str] | None = None,
    dictionaries: list[dict[str, Any]] | None = None,
    mappings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a combined context pack for multiple datasets.

    Each dataset gets a full context pack.  Shared dictionary refs and glossary
    items are deduplicated and lifted to the top level.
    """
    packs = [
        build_context_pack(ds, metrics=metrics, fields=fields, dictionaries=dictionaries, mappings=mappings)
        for ds in datasets
    ]

    all_dict_refs: list[list[str]] = [p.get("dictionary_refs", []) for p in packs]
    shared_refs = set(all_dict_refs[0]) if all_dict_refs else set()
    for refs in all_dict_refs[1:]:
        shared_refs &= set(refs)

    seen_glossary_keys: set[str] = set()
    shared_glossary: list[dict[str, Any]] = []
    for pack in packs:
        for item in pack.get("glossary", []):
            key = _as_text(item.get("key") or item.get("display_name"))
            if key and key not in seen_glossary_keys:
                seen_glossary_keys.add(key)
                shared_glossary.append(item)

    return {
        "mode": "multi",
        "datasets": packs,
        "shared_dictionary_refs": sorted(shared_refs),
        "shared_glossary": shared_glossary,
        "review_required": any(bool(pack.get("review_required")) for pack in packs),
    }
