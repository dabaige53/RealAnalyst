#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_io import (
    MetadataError,
    iter_dataset_files,
    iter_dictionary_files,
    iter_mapping_files,
    load_dataset_file,
    load_mapping_file,
    normalize_dataset,
)


REQUIRED_DATASET_KEYS = ("version", "id", "display_name", "source", "business", "maintenance", "fields")
REQUIRED_DICTIONARY_KEYS = ("version", "id", "kind", "display_name", "source_evidence")
REQUIRED_MAPPING_KEYS = ("version", "id", "kind", "source_id", "display_name", "source_evidence", "mappings")
ALLOWED_DEFINITION_SOURCE_TYPES = {"user_confirmed", "mapping_override", "dictionary", "industry_draft", "pending"}
PENDING_DEFINITION_TEXT = "业务定义待确认"
SCHEMA_ONLY_PHRASES = (
    "字段存在于 DuckDB 对象",
    "字段存在于 Tableau 对象",
    "来自 DuckDB 对象",
    "来自 Tableau 对象",
    "来自 DuckDB 表",
    "来自 DuckDB 视图",
    "来自 Tableau 视图",
    "的同名字段",
)


def require(mapping: dict[str, Any], key: str, errors: list[str], prefix: str) -> None:
    if key not in mapping or mapping.get(key) in (None, ""):
        errors.append(f"{prefix}.{key} is required")


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def validate_definition(
    definition: dict[str, Any],
    errors: list[str],
    prefix: str,
    *,
    subject_names: set[str] | None = None,
    enforce_semantic_text: bool = False,
) -> None:
    for key in ("text", "source_type", "confidence", "source_evidence", "needs_review"):
        require(definition, key, errors, prefix)
    text = _as_text(definition.get("text"))
    source_type = _as_text(definition.get("source_type"))
    if source_type and source_type not in ALLOWED_DEFINITION_SOURCE_TYPES:
        errors.append(f"{prefix}.source_type must be one of {sorted(ALLOWED_DEFINITION_SOURCE_TYPES)}")
    confidence = definition.get("confidence")
    if isinstance(confidence, (int, float)) and confidence < 0.7 and definition.get("needs_review") is not True:
        errors.append(f"{prefix}: low confidence definitions must set needs_review=true")
    evidence = definition.get("source_evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append(f"{prefix}.source_evidence must contain at least one evidence item")
    if definition.get("source_type") == "pending":
        if text != PENDING_DEFINITION_TEXT:
            errors.append(f"{prefix}: pending definitions must use text={PENDING_DEFINITION_TEXT!r}")
        if definition.get("needs_review") is not True:
            errors.append(f"{prefix}: pending definitions must set needs_review=true")
    if not enforce_semantic_text or text == PENDING_DEFINITION_TEXT:
        return
    if any(phrase in text for phrase in SCHEMA_ONLY_PHRASES):
        errors.append(f"{prefix}: connector schema notes are not valid business definitions")
    if subject_names and text in {name for name in subject_names if name}:
        errors.append(f"{prefix}: business definition must not equal only the field or metric name")


def validate_dataset(data: dict[str, Any], *, path: Path) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_DATASET_KEYS:
        require(data, key, errors, path.name)

    dataset = normalize_dataset(data, path=path)
    source = dataset.get("source")
    if not isinstance(source, dict):
        errors.append(f"{path.name}.source must be a mapping")
    else:
        require(source, "connector", errors, f"{path.name}.source")
        require(source, "object", errors, f"{path.name}.source")

    field_names: set[str] = set()
    for index, field in enumerate(dataset.get("fields", [])):
        prefix = f"{path.name}.fields[{index}]"
        if not isinstance(field, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        for key in ("name", "role", "type", "description"):
            require(field, key, errors, prefix)
        name = field.get("name")
        if isinstance(name, str):
            if name in field_names:
                errors.append(f"{prefix}.name duplicates field {name}")
            field_names.add(name)
        subject_names = {
            _as_text(field.get("name")),
            _as_text(field.get("display_name")),
            _as_text(field.get("physical_name")),
            _as_text(field.get("source_field")),
        }
        definition = field.get("business_definition")
        if isinstance(definition, dict):
            validate_definition(
                definition,
                errors,
                f"{prefix}.business_definition",
                subject_names=subject_names,
                enforce_semantic_text=True,
            )
        else:
            errors.append(f"{prefix}.business_definition is required")

    metric_names: set[str] = set()
    for index, metric in enumerate(dataset.get("metrics", [])):
        prefix = f"{path.name}.metrics[{index}]"
        if not isinstance(metric, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        for key in ("name", "expression", "description"):
            require(metric, key, errors, prefix)
        name = metric.get("name")
        if isinstance(name, str):
            if name in metric_names:
                errors.append(f"{prefix}.name duplicates metric {name}")
            metric_names.add(name)
        subject_names = {
            _as_text(metric.get("name")),
            _as_text(metric.get("display_name")),
            _as_text(metric.get("source_field")),
        }
        definition = metric.get("business_definition")
        if isinstance(definition, dict):
            validate_definition(
                definition,
                errors,
                f"{prefix}.business_definition",
                subject_names=subject_names,
                enforce_semantic_text=True,
            )
        else:
            errors.append(f"{prefix}.business_definition is required")
    return errors


def validate_dictionary(data: dict[str, Any], *, path: Path) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_DICTIONARY_KEYS:
        require(data, key, errors, path.name)
    if data.get("kind") != "dictionary":
        errors.append(f"{path.name}.kind must be dictionary")

    has_payload = any(isinstance(data.get(key), list) and data.get(key) for key in ("metrics", "fields", "glossary"))
    if not has_payload:
        errors.append(f"{path.name} must contain at least one of metrics, fields, or glossary")

    metric_names: set[str] = set()
    for index, metric in enumerate(data.get("metrics", []) or []):
        prefix = f"{path.name}.metrics[{index}]"
        if not isinstance(metric, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        for key in ("name", "display_name", "expression", "description"):
            require(metric, key, errors, prefix)
        name = metric.get("name")
        if isinstance(name, str):
            if name in metric_names:
                errors.append(f"{prefix}.name duplicates metric {name}")
            metric_names.add(name)
        definition = metric.get("business_definition")
        if isinstance(definition, dict):
            validate_definition(definition, errors, f"{prefix}.business_definition")
        else:
            errors.append(f"{prefix}.business_definition is required")

    field_names: set[str] = set()
    for index, field in enumerate(data.get("fields", []) or []):
        prefix = f"{path.name}.fields[{index}]"
        if not isinstance(field, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        for key in ("name", "display_name", "role", "type", "description"):
            require(field, key, errors, prefix)
        name = field.get("name")
        if isinstance(name, str):
            if name in field_names:
                errors.append(f"{prefix}.name duplicates field {name}")
            field_names.add(name)
        definition = field.get("business_definition")
        if isinstance(definition, dict):
            validate_definition(definition, errors, f"{prefix}.business_definition")
        else:
            errors.append(f"{prefix}.business_definition is required")

    glossary_keys: set[tuple[str, str]] = set()
    for index, term in enumerate(data.get("glossary", []) or []):
        prefix = f"{path.name}.glossary[{index}]"
        if not isinstance(term, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        for key in ("section", "key", "display_name", "definition"):
            require(term, key, errors, prefix)
        section = term.get("section")
        term_key = term.get("key")
        if isinstance(term_key, str):
            duplicate_key = (str(section or ""), term_key)
            if duplicate_key in glossary_keys:
                errors.append(f"{prefix}.key duplicates term {term_key} in section {section}")
            glossary_keys.add(duplicate_key)
        definition = term.get("business_definition")
        if isinstance(definition, dict):
            validate_definition(definition, errors, f"{prefix}.business_definition")
        else:
            errors.append(f"{prefix}.business_definition is required")
    return errors


def validate_mapping(data: dict[str, Any], *, path: Path) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_MAPPING_KEYS:
        require(data, key, errors, path.name)
    if data.get("kind") != "mapping":
        errors.append(f"{path.name}.kind must be mapping")
    mappings = data.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        errors.append(f"{path.name}.mappings must contain at least one item")
        return errors
    for index, item in enumerate(mappings):
        prefix = f"{path.name}.mappings[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        for key in ("type", "view_field", "standard_id"):
            require(item, key, errors, prefix)
        if item.get("type") not in ("field", "dimension", "metric"):
            errors.append(f"{prefix}.type must be field, dimension, or metric")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate LLM-native metadata YAML files.")
    parser.add_argument("--workspace", default=None, help="Workspace root. Defaults to discovered RealAnalyst root.")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    errors: list[str] = []
    dataset_files = list(iter_dataset_files(workspace))
    dictionary_files = list(iter_dictionary_files(workspace))
    mapping_files = list(iter_mapping_files(workspace))
    for path in dataset_files:
        try:
            errors.extend(validate_dataset(load_dataset_file(path), path=path))
        except MetadataError as exc:
            errors.append(str(exc))
    for path in dictionary_files:
        try:
            errors.extend(validate_dictionary(load_mapping_file(path), path=path))
        except MetadataError as exc:
            errors.append(str(exc))
    for path in mapping_files:
        try:
            errors.extend(validate_mapping(load_mapping_file(path), path=path))
        except MetadataError as exc:
            errors.append(str(exc))

    payload = {
        "success": not errors,
        "workspace": str(workspace),
        "checked_files": [str(path) for path in [*dataset_files, *dictionary_files, *mapping_files]],
        "dataset_count": len(dataset_files),
        "dictionary_count": len(dictionary_files),
        "mapping_count": len(mapping_files),
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
