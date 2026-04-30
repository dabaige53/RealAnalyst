#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from typing import Any

PENDING_DEFINITION_TEXT = "业务定义待确认"
SCHEMA_ONLY_PHRASES = (
    "来自 DuckDB 对象",
    "来自 Tableau 对象",
    "来自 DuckDB 表",
    "来自 DuckDB 视图",
    "来自 Tableau 视图",
    "的同名字段",
)


def as_text(value: Any) -> str:
    return str(value or "").strip()


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def is_schema_only_definition(text: str, subject_names: set[str] | None = None) -> bool:
    value = as_text(text)
    if not value:
        return False
    if any(phrase in value for phrase in SCHEMA_ONLY_PHRASES):
        return True
    return bool(subject_names and value in {name for name in subject_names if name})


def source_evidence(*items: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add_evidence(raw_items: Any) -> None:
        for evidence_item in as_list(raw_items):
            if not isinstance(evidence_item, dict):
                continue
            key = (as_text(evidence_item.get("type")), as_text(evidence_item.get("source")))
            if key in seen:
                continue
            seen.add(key)
            evidence.append(deepcopy(evidence_item))

    for item in items:
        direct_source = as_text(item.get("source"))
        if direct_source:
            direct = {"type": as_text(item.get("type")) or "document", "source": direct_source}
            key = (direct["type"], direct["source"])
            if key not in seen:
                seen.add(key)
                evidence.append(direct)
        add_evidence(item.get("source_evidence"))
        definition = item.get("business_definition")
        if isinstance(definition, dict):
            add_evidence(definition.get("source_evidence"))
    return evidence


def build_dictionary_indexes(dictionaries: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    indexes: dict[str, dict[str, dict[str, Any]]] = {"metrics": {}, "fields": {}, "glossary": {}}
    for dictionary in dictionaries:
        for metric in as_list(dictionary.get("metrics")):
            if not isinstance(metric, dict):
                continue
            for key in {as_text(metric.get("name")), as_text(metric.get("display_name")), *map(as_text, as_list(metric.get("synonyms")))}:
                if key:
                    indexes["metrics"].setdefault(key, metric)
        for field in as_list(dictionary.get("fields")):
            if not isinstance(field, dict):
                continue
            for key in {
                as_text(field.get("name")),
                as_text(field.get("display_name")),
                as_text(field.get("physical_name")),
                *map(as_text, as_list(field.get("synonyms"))),
            }:
                if key:
                    indexes["fields"].setdefault(key, field)
        for term in as_list(dictionary.get("glossary")):
            if not isinstance(term, dict):
                continue
            for key in {
                as_text(term.get("key")),
                as_text(term.get("display_name")),
                as_text(term.get("english_name")),
                *map(as_text, as_list(term.get("synonyms"))),
            }:
                if key:
                    indexes["glossary"].setdefault(key, term)
    return indexes


def mapping_by_source_field(mapping: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = as_list((mapping or {}).get("mappings"))
    evidence = as_list((mapping or {}).get("source_evidence"))
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not as_text(row.get("view_field")):
            continue
        item = dict(row)
        if evidence and not item.get("source_evidence"):
            item["source_evidence"] = deepcopy(evidence)
        result[as_text(item.get("view_field"))] = item
    return result


def find_dictionary_item(
    *,
    item: dict[str, Any],
    mapping: dict[str, Any] | None,
    role: str,
    indexes: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any] | None:
    keys = [
        as_text((mapping or {}).get("standard_id")),
        as_text((mapping or {}).get("field_id_or_override")),
        as_text(item.get("standard_id")),
        as_text(item.get("name")),
        as_text(item.get("display_name")),
        as_text(item.get("source_field")),
        as_text(item.get("physical_name")),
    ]
    buckets = ["metrics", "glossary"] if role == "metric" else ["fields", "glossary"]
    for bucket in buckets:
        for key in keys:
            if key and key in indexes[bucket]:
                return indexes[bucket][key]
    return None


def definition_from_item(item: dict[str, Any]) -> str:
    definition = item.get("business_definition")
    if isinstance(definition, dict) and as_text(definition.get("text")):
        return as_text(definition.get("text"))
    return as_text(item.get("description") or item.get("definition"))


def item_subject_names(*items: dict[str, Any] | None) -> set[str]:
    names: set[str] = set()
    for item in items:
        if not item:
            continue
        for key in ("name", "display_name", "physical_name", "source_field", "view_field", "standard_id", "field_id_or_override"):
            value = as_text(item.get(key))
            if value:
                names.add(value)
    return names


def enriched_definition(
    *,
    item: dict[str, Any],
    mapping: dict[str, Any] | None,
    dictionary_item: dict[str, Any] | None,
    role: str,
) -> tuple[dict[str, Any], str]:
    if mapping and as_text(mapping.get("definition_override")):
        text = as_text(mapping.get("definition_override"))
        if is_schema_only_definition(text, item_subject_names(item, mapping)):
            mapping = None
        else:
            return (
                {
                    "text": text,
                    "source_type": "mapping_override",
                    "confidence": 0.75,
                    "source_evidence": source_evidence(mapping),
                    "needs_review": False,
                },
                "mapping_override",
            )
    if dictionary_item:
        text = definition_from_item(dictionary_item)
        if text and not is_schema_only_definition(text, item_subject_names(item, mapping, dictionary_item)):
            source_definition = dictionary_item.get("business_definition") if isinstance(dictionary_item.get("business_definition"), dict) else {}
            return (
                {
                    "text": text,
                    "source_type": "dictionary",
                    "confidence": source_definition.get("confidence", 0.85),
                    "source_evidence": source_evidence(dictionary_item),
                    "needs_review": bool(source_definition.get("needs_review", False)),
                },
                "dictionary",
            )
    if role == "field":
        evidence = as_list((item.get("business_definition") or {}).get("source_evidence"))
        return (
            {
                "text": PENDING_DEFINITION_TEXT,
                "source_type": "pending",
                "confidence": 0.0,
                "source_evidence": evidence or [{"type": "metadata", "source": "metadata/datasets"}],
                "needs_review": True,
            },
            "pending",
        )
    evidence = as_list((item.get("business_definition") or {}).get("source_evidence"))
    return (
        {
            "text": PENDING_DEFINITION_TEXT,
            "source_type": "pending",
            "confidence": 0.0,
            "source_evidence": evidence or [{"type": "metadata", "source": "metadata/datasets"}],
            "needs_review": True,
        },
        "pending",
    )
