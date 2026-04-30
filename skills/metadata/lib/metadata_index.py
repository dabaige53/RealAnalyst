#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _definition_text(item: dict[str, Any]) -> str:
    definition = item.get("business_definition")
    if isinstance(definition, dict):
        return _as_text(definition.get("text"))
    return ""


def _definition_source(item: dict[str, Any]) -> str:
    definition = item.get("business_definition")
    if isinstance(definition, dict):
        return _as_text(definition.get("source_type"))
    return ""


def dataset_record(dataset: dict[str, Any]) -> dict[str, Any]:
    business = dataset.get("business") if isinstance(dataset.get("business"), dict) else {}
    source = dataset.get("source") if isinstance(dataset.get("source"), dict) else {}
    return {
        "record_type": "dataset",
        "dataset_id": _as_text(dataset.get("id") or dataset.get("source_id")),
        "display_name": _as_text(dataset.get("display_name")),
        "description": _as_text(dataset.get("description") or business.get("description")),
        "domain": _as_text(business.get("domain")),
        "source_connector": _as_text(source.get("connector")),
        "source_object": _as_text(source.get("object")),
        "grain": _as_list(business.get("grain")),
        "primary_key": _as_list(business.get("primary_key")),
        "time_fields": _as_list(business.get("time_fields")),
        "sample_questions": _as_list(business.get("sample_questions")),
    }


def field_records(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    dataset_id = _as_text(dataset.get("id") or dataset.get("source_id"))
    records: list[dict[str, Any]] = []
    for field in _as_list(dataset.get("fields")):
        if not isinstance(field, dict):
            continue
        records.append(
            {
                "record_type": "field",
                "dataset_id": dataset_id,
                "field_name": _as_text(field.get("name")),
                "physical_name": _as_text(field.get("physical_name")),
                "display_name": _as_text(field.get("display_name")),
                "role": _as_text(field.get("role")),
                "type": _as_text(field.get("type")),
                "description": _as_text(field.get("description")),
                "definition": _definition_text(field),
                "definition_source": _definition_source(field),
                "schema_note": _as_text(field.get("schema_note")),
                "synonyms": _as_list(field.get("synonyms")),
                "sensitive_level": _as_text(field.get("sensitive_level")),
            }
        )
    return records


def metric_records(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    dataset_id = _as_text(dataset.get("id") or dataset.get("source_id"))
    records: list[dict[str, Any]] = []
    for metric in _as_list(dataset.get("metrics")):
        if not isinstance(metric, dict):
            continue
        records.append(
            {
                "record_type": "metric",
                "dataset_id": dataset_id,
                "metric_name": _as_text(metric.get("name")),
                "display_name": _as_text(metric.get("display_name")),
                "expression": _as_text(metric.get("expression")),
                "aggregation": _as_text(metric.get("aggregation")),
                "unit": _as_text(metric.get("unit")),
                "valid_grains": _as_list(metric.get("valid_grains")),
                "description": _as_text(metric.get("description")),
                "definition": _definition_text(metric),
                "definition_source": _definition_source(metric),
                "schema_note": _as_text(metric.get("schema_note")),
                "synonyms": _as_list(metric.get("synonyms")),
            }
        )
    return records


def glossary_records(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    dataset_id = _as_text(dataset.get("id") or dataset.get("source_id"))
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_terms(entity_type: str, entity_name: str, terms: Iterable[Any]) -> None:
        for value in terms:
            term = _as_text(value)
            if not term:
                continue
            key = (entity_type, entity_name, term.casefold())
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "record_type": "glossary",
                    "dataset_id": dataset_id,
                    "term": term,
                    "entity_type": entity_type,
                    "entity_name": entity_name,
                }
            )

    for field in _as_list(dataset.get("fields")):
        if not isinstance(field, dict):
            continue
        field_name = _as_text(field.get("name"))
        add_terms("field", field_name, [field_name, field.get("display_name"), *_as_list(field.get("synonyms"))])

    for metric in _as_list(dataset.get("metrics")):
        if not isinstance(metric, dict):
            continue
        metric_name = _as_text(metric.get("name"))
        add_terms("metric", metric_name, [metric_name, metric.get("display_name"), *_as_list(metric.get("synonyms"))])

    for glossary_item in _as_list(dataset.get("glossary")):
        if not isinstance(glossary_item, dict):
            continue
        entity_name = _as_text(glossary_item.get("key") or glossary_item.get("item_key") or glossary_item.get("display_name"))
        add_terms(
            "glossary",
            entity_name,
            [
                entity_name,
                glossary_item.get("display_name"),
                glossary_item.get("english_name"),
                glossary_item.get("definition"),
                *_as_list(glossary_item.get("synonyms")),
                *_as_list(glossary_item.get("values")),
            ],
        )

    return records


def dictionary_records(dictionary: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    dictionary_id = _as_text(dictionary.get("id") or dictionary.get("dictionary_id"))
    dictionary_dataset = {
        "id": dictionary_id,
        "fields": _as_list(dictionary.get("fields")),
        "metrics": _as_list(dictionary.get("metrics")),
        "glossary": _as_list(dictionary.get("glossary")),
    }
    return {
        "fields": field_records(dictionary_dataset),
        "metrics": metric_records(dictionary_dataset),
        "glossary": glossary_records(dictionary_dataset),
    }


def mapping_records(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    mapping_id = _as_text(mapping.get("id") or mapping.get("mapping_id"))
    source_id = _as_text(mapping.get("source_id") or mapping.get("source"))
    records: list[dict[str, Any]] = []
    for item in _as_list(mapping.get("mappings")):
        if not isinstance(item, dict):
            continue
        records.append(
            {
                "record_type": "mapping",
                "mapping_id": mapping_id,
                "source_id": source_id,
                "mapping_type": _as_text(item.get("type")),
                "view_field": _as_text(item.get("view_field")),
                "standard_id": _as_text(item.get("standard_id")),
                "field_id_or_override": _as_text(item.get("field_id_or_override")),
                "definition_override": _as_text(item.get("definition_override")),
                "notes": _as_text(item.get("notes")),
            }
        )
    return records


def build_all_indexes(
    datasets: Iterable[dict[str, Any]],
    dictionaries: Iterable[dict[str, Any]] = (),
    mappings: Iterable[dict[str, Any]] = (),
) -> dict[str, list[dict[str, Any]]]:
    indexes: dict[str, list[dict[str, Any]]] = {
        "datasets": [],
        "fields": [],
        "metrics": [],
        "glossary": [],
        "mappings": [],
    }
    for dataset in datasets:
        indexes["datasets"].append(dataset_record(dataset))
        indexes["fields"].extend(field_records(dataset))
        indexes["metrics"].extend(metric_records(dataset))
        indexes["glossary"].extend(glossary_records(dataset))
    for dictionary in dictionaries:
        records = dictionary_records(dictionary)
        indexes["fields"].extend(records["fields"])
        indexes["metrics"].extend(records["metrics"])
        indexes["glossary"].extend(records["glossary"])
    for mapping in mappings:
        indexes["mappings"].extend(mapping_records(mapping))
    return indexes


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _fts5_row(record: dict[str, Any]) -> tuple[str, str, str, str, str, str, str, str, str]:
    """Convert any index record into a flat tuple for the FTS5 search_index table."""
    record_type = _as_text(record.get("record_type"))
    dataset_id = _as_text(record.get("dataset_id") or record.get("source_id") or record.get("mapping_id"))
    name = _as_text(
        record.get("field_name")
        or record.get("metric_name")
        or record.get("term")
        or record.get("view_field")
        or record.get("display_name")
    )
    display_name = _as_text(record.get("display_name"))
    description = _as_text(record.get("description"))
    definition = _as_text(record.get("definition") or record.get("definition_override"))
    synonyms = " ".join(_as_text(s) for s in _as_list(record.get("synonyms")))
    extra_parts: list[str] = []
    for key in ("role", "type", "domain", "expression", "aggregation", "unit", "notes",
                "schema_note", "source_connector", "source_object", "mapping_type",
                "standard_id", "entity_type", "entity_name"):
        v = _as_text(record.get(key))
        if v:
            extra_parts.append(v)
    for key in ("grain", "primary_key", "time_fields", "sample_questions", "valid_grains"):
        for item in _as_list(record.get(key)):
            v = _as_text(item)
            if v:
                extra_parts.append(v)
    extra_text = " ".join(extra_parts)
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True)
    return (record_type, dataset_id, name, display_name, description, definition, synonyms, extra_text, payload)


def write_fts5_index(db_path: Path, indexes: dict[str, list[dict[str, Any]]]) -> None:
    """Write all index records into a SQLite FTS5 database at *db_path*."""
    import sqlite3

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
                record_type,
                dataset_id,
                name,
                display_name,
                description,
                definition,
                synonyms,
                extra_text,
                payload UNINDEXED,
                tokenize='unicode61'
            );
            """
        )
        rows: list[tuple[str, ...]] = []
        for records in indexes.values():
            for record in records:
                rows.append(_fts5_row(record))
        conn.executemany(
            "INSERT INTO search_index(record_type, dataset_id, name, display_name, description, definition, synonyms, extra_text, payload) VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
