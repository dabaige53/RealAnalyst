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


def _source_type(item: dict[str, Any]) -> str:
    definition = item.get("business_definition")
    if isinstance(definition, dict):
        return _as_text(definition.get("source_type"))
    return ""


def _definition_ref(item: dict[str, Any]) -> str:
    definition = item.get("business_definition")
    if isinstance(definition, dict):
        return _as_text(definition.get("ref"))
    return ""


def _canonical_key(item: dict[str, Any]) -> str:
    return _as_text(item.get("name") or item.get("key") or item.get("item_key") or item.get("display_name"))


def _alias_values(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for key in ("aliases", "synonyms"):
        for value in _as_list(item.get(key)):
            alias = _as_text(value)
            if alias and alias.casefold() not in seen:
                seen.add(alias.casefold())
                values.append(alias)
    return values


def _dictionary_ref(dictionary_id: str, item_key: str) -> str:
    return ".".join(part for part in (dictionary_id, item_key) if part)


def _dictionary_entity_index(dictionaries: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    sections = (("metrics", "metric"), ("fields", "field"), ("glossary", "glossary"))
    for dictionary in dictionaries:
        dictionary_id = _as_text(dictionary.get("id") or dictionary.get("dictionary_id"))
        if not dictionary_id:
            continue
        for section, entity_type in sections:
            for item in _as_list(dictionary.get(section)):
                if not isinstance(item, dict):
                    continue
                item_key = _canonical_key(item)
                if not item_key:
                    continue
                entity = dict(item)
                ref = _dictionary_ref(dictionary_id, item_key)
                entity["_dictionary_id"] = dictionary_id
                entity["_entity_type"] = entity_type
                entity["_canonical_name"] = item_key
                entity["_ref"] = ref
                for key in {
                    item_key,
                    _as_text(item.get("name")),
                    _as_text(item.get("key")),
                    _as_text(item.get("display_name")),
                    ref,
                    f"dictionary:{dictionary_id}:{item_key}",
                }:
                    if key:
                        index.setdefault(key, entity)
    return index


def _mapping_by_dataset_standard(mappings: Iterable[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for mapping in mappings:
        source_id = _as_text(mapping.get("source_id") or mapping.get("source"))
        if not source_id:
            continue
        for item in _as_list(mapping.get("mappings")):
            if not isinstance(item, dict):
                continue
            standard_id = _as_text(item.get("standard_id"))
            if standard_id:
                index.setdefault((source_id, standard_id), item)
    return index


def _dictionary_entity_for_item(item: dict[str, Any], dictionary_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for key in (_definition_ref(item), _as_text(item.get("name")), _as_text(item.get("display_name")), _as_text(item.get("physical_name"))):
        if key and key in dictionary_index:
            return dictionary_index[key]
    return None


def _field_physical_name(dataset_id: str, field: dict[str, Any], mapping_index: dict[tuple[str, str], dict[str, Any]]) -> str:
    mapping = mapping_index.get((dataset_id, _as_text(field.get("name"))), {})
    return _as_text(field.get("physical_name") or mapping.get("view_field") or field.get("name"))


def _metric_physical_name(dataset_id: str, metric: dict[str, Any], mapping_index: dict[tuple[str, str], dict[str, Any]]) -> str:
    mapping = mapping_index.get((dataset_id, _as_text(metric.get("name"))), {})
    return _as_text(metric.get("physical_name") or mapping.get("view_field"))


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
                "source_type": _source_type(field),
                "ref": _definition_ref(field),
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
                "source_type": _source_type(metric),
                "ref": _definition_ref(metric),
            }
        )
    return records


def alias_records(
    datasets: Iterable[dict[str, Any]],
    dictionaries: Iterable[dict[str, Any]],
    mappings: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    dictionary_index = _dictionary_entity_index(dictionaries)
    mapping_index = _mapping_by_dataset_standard(mappings)
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add_aliases(dataset_id: str, entity_type: str, item: dict[str, Any], physical_name: str) -> None:
        entity = _dictionary_entity_for_item(item, dictionary_index)
        if not entity:
            return
        canonical_name = _as_text(item.get("name")) or _as_text(entity.get("_canonical_name"))
        canonical_display_name = _as_text(item.get("display_name") or entity.get("display_name"))
        ref = _definition_ref(item) or _as_text(entity.get("_ref"))
        alias_source = _as_text(entity.get("_ref")) or ref
        excluded = {value.casefold() for value in (canonical_name, canonical_display_name, physical_name) if value}
        for alias in _alias_values(entity):
            if alias.casefold() in excluded:
                continue
            key = (dataset_id, entity_type, canonical_name, alias.casefold())
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "record_type": "alias",
                    "dataset_id": dataset_id,
                    "entity_type": entity_type,
                    "alias": alias,
                    "matched_alias": alias,
                    "match_reason": "alias",
                    "alias_source": alias_source,
                    "canonical_name": canonical_name,
                    "canonical_display_name": canonical_display_name,
                    "display_name": canonical_display_name,
                    "physical_name": physical_name,
                    "ref": ref,
                }
            )

    for dataset in datasets:
        dataset_id = _as_text(dataset.get("id") or dataset.get("source_id"))
        if not dataset_id:
            continue
        for field in _as_list(dataset.get("fields")):
            if isinstance(field, dict):
                add_aliases(dataset_id, "field", field, _field_physical_name(dataset_id, field, mapping_index))
        for metric in _as_list(dataset.get("metrics")):
            if isinstance(metric, dict):
                add_aliases(dataset_id, "metric", metric, _metric_physical_name(dataset_id, metric, mapping_index))

    for dictionary in dictionaries:
        dictionary_id = _as_text(dictionary.get("id") or dictionary.get("dictionary_id"))
        if not dictionary_id:
            continue
        for item in _as_list(dictionary.get("glossary")):
            if not isinstance(item, dict):
                continue
            canonical_name = _canonical_key(item)
            if not canonical_name:
                continue
            canonical_display_name = _as_text(item.get("display_name")) or canonical_name
            ref = _dictionary_ref(dictionary_id, canonical_name)
            excluded = {value.casefold() for value in (canonical_name, canonical_display_name) if value}
            for alias in _alias_values(item):
                if alias.casefold() in excluded:
                    continue
                key = (dictionary_id, "glossary", canonical_name, alias.casefold())
                if key in seen:
                    continue
                seen.add(key)
                records.append(
                    {
                        "record_type": "alias",
                        "dataset_id": dictionary_id,
                        "entity_type": "glossary",
                        "alias": alias,
                        "matched_alias": alias,
                        "match_reason": "alias",
                        "alias_source": ref,
                        "canonical_name": canonical_name,
                        "canonical_display_name": canonical_display_name,
                        "display_name": canonical_display_name,
                        "physical_name": "",
                        "ref": ref,
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
        add_terms("field", field_name, [field_name, field.get("display_name")])

    for metric in _as_list(dataset.get("metrics")):
        if not isinstance(metric, dict):
            continue
        metric_name = _as_text(metric.get("name"))
        add_terms("metric", metric_name, [metric_name, metric.get("display_name")])

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
    dataset_list = list(datasets)
    dictionary_list = list(dictionaries)
    mapping_list = list(mappings)
    indexes: dict[str, list[dict[str, Any]]] = {
        "datasets": [],
        "fields": [],
        "metrics": [],
        "glossary": [],
        "mappings": [],
        "aliases": [],
    }
    for dataset in dataset_list:
        indexes["datasets"].append(dataset_record(dataset))
        indexes["fields"].extend(field_records(dataset))
        indexes["metrics"].extend(metric_records(dataset))
        indexes["glossary"].extend(glossary_records(dataset))
    for dictionary in dictionary_list:
        records = dictionary_records(dictionary)
        indexes["fields"].extend(records["fields"])
        indexes["metrics"].extend(records["metrics"])
        indexes["glossary"].extend(records["glossary"])
    for mapping in mapping_list:
        indexes["mappings"].extend(mapping_records(mapping))
    indexes["aliases"].extend(alias_records(dataset_list, dictionary_list, mapping_list))
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
        or record.get("matched_alias")
        or record.get("alias")
        or record.get("canonical_name")
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
                "source_connector", "source_object", "mapping_type",
                "standard_id", "entity_type", "entity_name", "matched_alias",
                "alias_source", "canonical_name", "canonical_display_name",
                "physical_name", "ref", "match_reason"):
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
