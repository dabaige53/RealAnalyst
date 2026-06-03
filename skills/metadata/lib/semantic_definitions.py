#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

PENDING_DEFINITION_TEXT = "业务定义待确认"
SEMANTIC_REF_LABELS = {
    "standard_ref": "标准定义引用",
    "mapping_ref": "映射覆盖引用",
    "local_confirmed": "本地确认口径",
    "local_draft": "本地草稿口径",
    "inferred": "推断口径",
    "pending": "待补齐",
    "local_only": "未引用标准语义",
}
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


def semantic_ref_status(source_type: str, ref: str = "") -> str:
    source_type = as_text(source_type)
    ref = as_text(ref)
    if source_type == "dictionary":
        return "standard_ref"
    if source_type == "mapping_override":
        return "mapping_ref"
    if source_type == "user_confirmed":
        return "local_confirmed"
    if source_type == "industry_draft":
        return "local_draft"
    if source_type == "inferred":
        return "inferred"
    if source_type == "pending":
        return "pending"
    if ref.startswith("mapping:"):
        return "mapping_ref"
    if ref:
        return "standard_ref"
    return "local_only"


def semantic_ref_payload(
    definition: dict[str, Any] | None,
    *,
    ref: str = "",
    source_layer: str = "",
) -> dict[str, Any]:
    definition = definition if isinstance(definition, dict) else {}
    source_type = as_text(definition.get("source_type"))
    resolved_ref = as_text(ref or definition.get("ref"))
    status = semantic_ref_status(source_type, resolved_ref)
    return {
        "status": status,
        "label": SEMANTIC_REF_LABELS[status],
        "ref": resolved_ref,
        "source_type": source_type,
        "source_layer": as_text(source_layer),
        "confidence": definition.get("confidence"),
        "needs_review": bool(definition.get("needs_review")),
    }


def is_schema_only_definition(text: str, subject_names: set[str] | None = None) -> bool:
    value = as_text(text)
    if not value:
        return False
    if any(phrase in value for phrase in SCHEMA_ONLY_PHRASES):
        return True
    return bool(subject_names and value in {name for name in subject_names if name})


def dictionary_ref(dictionary_item: dict[str, Any]) -> str:
    dictionary_id = as_text(dictionary_item.get("_dictionary_id"))
    item_id = as_text(dictionary_item.get("name") or dictionary_item.get("key") or dictionary_item.get("display_name"))
    return ".".join(part for part in (dictionary_id, item_id) if part)


def mapping_ref(mapping: dict[str, Any]) -> str:
    mapping_id = as_text(mapping.get("_mapping_id"))
    item_id = as_text(mapping.get("standard_id") or mapping.get("view_field") or mapping.get("field_id_or_override"))
    if mapping_id and item_id:
        return f"mapping:{mapping_id}:{item_id}"
    return f"mapping:{mapping_id or item_id}"


def build_dictionary_indexes(dictionaries: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    indexes: dict[str, dict[str, dict[str, Any]]] = {"metrics": {}, "fields": {}, "glossary": {}}
    for dictionary in dictionaries:
        dictionary_id = as_text(dictionary.get("id"))
        for metric in as_list(dictionary.get("metrics")):
            if not isinstance(metric, dict):
                continue
            metric = dict(metric)
            metric["_dictionary_id"] = dictionary_id
            for key in {
                as_text(metric.get("name")),
                as_text(metric.get("display_name")),
                *map(as_text, as_list(metric.get("aliases"))),
                *map(as_text, as_list(metric.get("synonyms"))),
            }:
                if key:
                    indexes["metrics"].setdefault(key, metric)
        for field in as_list(dictionary.get("fields")):
            if not isinstance(field, dict):
                continue
            field = dict(field)
            field["_dictionary_id"] = dictionary_id
            for key in {
                as_text(field.get("name")),
                as_text(field.get("display_name")),
                as_text(field.get("physical_name")),
                *map(as_text, as_list(field.get("aliases"))),
                *map(as_text, as_list(field.get("synonyms"))),
            }:
                if key:
                    indexes["fields"].setdefault(key, field)
        for term in as_list(dictionary.get("glossary")):
            if not isinstance(term, dict):
                continue
            term = dict(term)
            term["_dictionary_id"] = dictionary_id
            for key in {
                as_text(term.get("key")),
                as_text(term.get("display_name")),
                as_text(term.get("english_name")),
                *map(as_text, as_list(term.get("aliases"))),
                *map(as_text, as_list(term.get("synonyms"))),
            }:
                if key:
                    indexes["glossary"].setdefault(key, term)
    return indexes


def mapping_by_source_field(mapping: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = as_list((mapping or {}).get("mappings"))
    mapping_id = as_text((mapping or {}).get("id"))
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not as_text(row.get("view_field")):
            continue
        item = dict(row)
        item["_mapping_id"] = mapping_id
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
        as_text(item.get("name")),
        as_text(item.get("display_name")),
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
                    "ref": mapping_ref(mapping),
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
                    "ref": dictionary_ref(dictionary_item),
                    "needs_review": bool(source_definition.get("needs_review", False)),
                },
                "dictionary",
            )
    if role == "field":
        return (
            {
                "text": PENDING_DEFINITION_TEXT,
                "source_type": "pending",
                "confidence": 0.0,
                "needs_review": True,
            },
            "pending",
        )
    return (
        {
            "text": PENDING_DEFINITION_TEXT,
            "source_type": "pending",
            "confidence": 0.0,
            "needs_review": True,
        },
        "pending",
    )
