#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_io import (  # noqa: E402
    iter_dictionary_files,
    load_dataset_file,
    load_mapping_file,
    resolve_dataset_path,
)
from skills.metadata.lib.semantic_definitions import (  # noqa: E402
    as_text,
    build_dictionary_indexes,
    enriched_definition,
    find_dictionary_item,
    is_schema_only_definition,
    mapping_by_source_field,
)


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


def _load_mapping(workspace: Path, dataset: dict[str, Any]) -> dict[str, Any]:
    mapping_ref = as_text(dataset.get("mapping_ref"))
    if not mapping_ref:
        return {}
    path = workspace / "metadata" / "mappings" / f"{mapping_ref}.yaml"
    return load_mapping_file(path) if path.exists() else {}


LEGACY_SCHEMA_PHRASES = (
    "字段存在于 DuckDB 对象",
    "字段存在于 Tableau 对象",
    "来自 DuckDB 对象",
    "来自 Tableau 对象",
    "来自 DuckDB 表",
    "来自 DuckDB 视图",
    "来自 Tableau 视图",
)


def _clean_legacy_schema_notes(item: dict[str, Any]) -> None:
    item.pop("schema_note", None)
    description = as_text(item.get("description"))
    subject_names = {
        as_text(item.get("name")),
        as_text(item.get("display_name")),
        as_text(item.get("source_field")),
        as_text(item.get("physical_name")),
    }
    if is_schema_only_definition(description, subject_names) or any(phrase in description for phrase in LEGACY_SCHEMA_PHRASES):
        display_name = as_text(item.get("display_name") or item.get("source_field") or item.get("physical_name") or item.get("name"))
        item["description"] = f"{display_name} 的业务定义待确认。"


def _subject_names(item: dict[str, Any]) -> set[str]:
    return {
        as_text(item.get("name")),
        as_text(item.get("display_name")),
        as_text(item.get("source_field")),
        as_text(item.get("physical_name")),
    }


def _existing_definition(item: dict[str, Any]) -> dict[str, Any]:
    definition = item.get("business_definition")
    return definition if isinstance(definition, dict) else {}


def _definition_needs_enrichment(item: dict[str, Any]) -> bool:
    definition = _existing_definition(item)
    text = as_text(definition.get("text"))
    if not text:
        return True
    if as_text(definition.get("source_type")) == "pending":
        return True
    return is_schema_only_definition(text, _subject_names(item))


def _source_type_for_existing(item: dict[str, Any], fallback: str) -> str:
    definition = _existing_definition(item)
    source_type = as_text(definition.get("source_type") or item.get("definition_source"))
    return source_type or fallback


def _apply_definition(item: dict[str, Any], definition: dict[str, Any], source_type: str) -> bool:
    if _definition_needs_enrichment(item):
        item["business_definition"] = definition
        item["definition_source"] = source_type
        return True
    source_type = _source_type_for_existing(item, "industry_draft")
    item["business_definition"]["source_type"] = source_type
    item["definition_source"] = source_type
    return False


def enrich_dataset(workspace: Path, dataset_id: str) -> dict[str, Any]:
    path = resolve_dataset_path(workspace, dataset_id)
    dataset = load_dataset_file(path)
    mapping = _load_mapping(workspace, dataset)
    mapping_index = mapping_by_source_field(mapping)
    dictionaries = [load_mapping_file(item) for item in iter_dictionary_files(workspace)]
    dictionary_indexes = build_dictionary_indexes(dictionaries)
    updated_fields = 0
    updated_metrics = 0
    pending_fields = 0
    pending_metrics = 0

    for field in dataset.get("fields") or []:
        if not isinstance(field, dict):
            continue
        source_field = as_text(field.get("source_field") or field.get("physical_name"))
        mapping_item = mapping_index.get(source_field)
        dictionary_item = find_dictionary_item(item=field, mapping=mapping_item, role="field", indexes=dictionary_indexes)
        definition, source_type = enriched_definition(item=field, mapping=mapping_item, dictionary_item=dictionary_item, role="field")
        changed = _apply_definition(field, definition, source_type)
        _clean_legacy_schema_notes(field)
        if changed:
            updated_fields += 1
        if as_text(_existing_definition(field).get("source_type")) == "pending":
            pending_fields += 1

    for metric in dataset.get("metrics") or []:
        if not isinstance(metric, dict):
            continue
        source_field = as_text(metric.get("source_field"))
        mapping_item = mapping_index.get(source_field)
        dictionary_item = find_dictionary_item(item=metric, mapping=mapping_item, role="metric", indexes=dictionary_indexes)
        definition, source_type = enriched_definition(item=metric, mapping=mapping_item, dictionary_item=dictionary_item, role="metric")
        changed = _apply_definition(metric, definition, source_type)
        if dictionary_item:
            if not as_text(metric.get("unit")) and as_text(dictionary_item.get("unit")):
                metric["unit"] = as_text(dictionary_item.get("unit"))
            if as_text(metric.get("aggregation")) == "source_defined" and as_text(dictionary_item.get("aggregation")):
                metric["aggregation"] = as_text(dictionary_item.get("aggregation"))
            if as_text(dictionary_item.get("expression")) and as_text(metric.get("expression")).startswith("source_field:"):
                metric["standard_expression"] = as_text(dictionary_item.get("expression"))
        _clean_legacy_schema_notes(metric)
        if changed:
            updated_metrics += 1
        if as_text(_existing_definition(metric).get("source_type")) == "pending":
            pending_metrics += 1

    path.write_text(yaml.dump(dataset, Dumper=NoAliasDumper, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {
        "dataset_id": dataset_id,
        "path": str(path),
        "updated_fields": updated_fields,
        "updated_metrics": updated_metrics,
        "pending_fields": pending_fields,
        "pending_metrics": pending_metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich dataset business definitions from mappings and dictionaries.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--dataset-id", action="append", default=[])
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    if not args.dataset_id:
        print(json.dumps({"success": False, "error": "--dataset-id is required"}, ensure_ascii=False, indent=2))
        return 2
    results = [enrich_dataset(workspace, dataset_id) for dataset_id in args.dataset_id]
    print(json.dumps({"success": True, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
