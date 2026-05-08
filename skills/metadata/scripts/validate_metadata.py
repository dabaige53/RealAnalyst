#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
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
from skills.metadata.lib.metadata_completeness import completeness_findings, load_dataset_mappings


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
DATASET_FORBIDDEN_KEYS = {
    "sample_profile": "profile output belongs in metadata/sources/refine or runtime registry, not dataset YAML",
    "sample_values": "sample values belong in metadata/sources/refine or runtime registry, not dataset YAML",
    "top_values": "value profiles belong in metadata/sources/refine or runtime registry, not dataset YAML",
    "enum_values": "enumerations belong in dictionaries or runtime registry, not dataset YAML",
    "source_mapping": "source mappings belong in metadata/mappings/*.yaml, not dataset YAML",
    "definition_source": "use business_definition.source_type instead of definition_source",
    "duckdb_type": "physical type snapshots belong in connector snapshots or runtime registry; use semantic type instead",
    "nullable": "nullable flags belong in connector snapshots or runtime registry, not dataset YAML",
}
DATASET_FORBIDDEN_EVIDENCE_KEYS = {
    "source_evidence": "dataset field/metric definitions must use business_definition.ref; evidence belongs in metadata/audit, dictionaries, mappings, or sources",
    "quote": "audit quotes belong in metadata/audit, dictionaries, mappings, or sources, not dataset YAML",
    "source": "audit source paths belong in metadata/audit, dictionaries, mappings, or sources, not dataset field/metric definitions",
    "document_path": "document paths belong in metadata/audit or sources, not dataset YAML",
}
DATASET_WARN_LINES = 1000
DATASET_MAX_LINES = 1500
SEMANTIC_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def require(mapping: dict[str, Any], key: str, errors: list[str], prefix: str) -> None:
    if key not in mapping or mapping.get(key) in (None, ""):
        errors.append(f"{prefix}.{key} is required")


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _walk(value: Any, prefix: str) -> list[tuple[str, Any]]:
    items = [(prefix, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            items.extend(_walk(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk(child, f"{prefix}[{index}]"))
    return items


def validate_semantic_name(value: Any, errors: list[str], prefix: str, *, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        return
    if not SEMANTIC_NAME_RE.match(value.strip()):
        errors.append(
            f"{prefix}: {label} must be a stable semantic id using ASCII letters, digits, '_' or '.'; "
            "put user-facing names in display_name and physical source columns in physical_name/source_field"
        )


def validate_dataset_responsibility(data: dict[str, Any], errors: list[str], *, path: Path) -> None:
    try:
        line_count = len(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        line_count = 0
    if line_count > DATASET_MAX_LINES:
        errors.append(
            f"{path.name}: dataset YAML has {line_count} lines; keep datasets semantic-only and move profiles, enums, "
            f"registry snapshots, and repeated evidence out of metadata/datasets"
        )

    for item_path, value in _walk(data, path.name):
        if not isinstance(value, dict):
            continue
        for key, reason in DATASET_FORBIDDEN_KEYS.items():
            if key in value:
                errors.append(f"{item_path}.{key}: {reason}")
        if item_path.endswith(".fields") or item_path.endswith(".metrics"):
            continue
        if ".fields[" in item_path or ".metrics[" in item_path:
            for key, reason in DATASET_FORBIDDEN_EVIDENCE_KEYS.items():
                if key in value:
                    errors.append(f"{item_path}.{key}: {reason}")


def dataset_size_warnings(*, path: Path) -> list[str]:
    try:
        line_count = len(path.read_text(encoding="utf-8").splitlines())
    except OSError:
        return []
    if DATASET_WARN_LINES < line_count <= DATASET_MAX_LINES:
        return [
            f"{path.name}: dataset YAML has {line_count} lines; check whether profile, enum, mapping, registry, "
            f"or repeated evidence data should be moved out"
        ]
    return []


def validate_definition(
    definition: dict[str, Any],
    errors: list[str],
    prefix: str,
    *,
    subject_names: set[str] | None = None,
    enforce_semantic_text: bool = False,
    description: str = "",
    require_evidence: bool = True,
    allow_evidence: bool = True,
    require_ref: bool = False,
) -> None:
    required_keys = ["text", "source_type", "confidence", "needs_review"]
    if require_evidence:
        required_keys.append("source_evidence")
    for key in required_keys:
        require(definition, key, errors, prefix)
    text = _as_text(definition.get("text"))
    source_type = _as_text(definition.get("source_type"))
    if source_type and source_type not in ALLOWED_DEFINITION_SOURCE_TYPES:
        errors.append(f"{prefix}.source_type must be one of {sorted(ALLOWED_DEFINITION_SOURCE_TYPES)}")
    confidence = definition.get("confidence")
    if isinstance(confidence, (int, float)) and confidence < 0.7 and definition.get("needs_review") is not True:
        errors.append(f"{prefix}: low confidence definitions must set needs_review=true")
    if "source_evidence" in definition and not allow_evidence:
        errors.append(f"{prefix}.source_evidence: dataset definitions must use ref instead of expanded evidence")
    evidence = definition.get("source_evidence")
    if require_evidence and (not isinstance(evidence, list) or not evidence):
        errors.append(f"{prefix}.source_evidence must contain at least one evidence item")
    if require_ref and source_type in {"dictionary", "mapping_override"} and not _as_text(definition.get("ref")):
        errors.append(f"{prefix}.ref is required when source_type={source_type}")
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
    if description and text == _as_text(description):
        errors.append(f"{prefix}: business definition must not duplicate description")


def validate_dataset(data: dict[str, Any], *, path: Path) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_DATASET_KEYS:
        require(data, key, errors, path.name)
    validate_dataset_responsibility(data, errors, path=path)

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
            validate_semantic_name(name, errors, f"{prefix}.name", label="field name")
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
                description=_as_text(field.get("description")),
                require_evidence=False,
                allow_evidence=False,
                require_ref=True,
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
            validate_semantic_name(name, errors, f"{prefix}.name", label="metric name")
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
                description=_as_text(metric.get("description")),
                require_evidence=False,
                allow_evidence=False,
                require_ref=True,
            )
            if definition.get("source_type") == "pending":
                errors.append(f"{prefix}.business_definition: pending definitions must not be registered as formal metrics")
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


def validate_completeness(workspace: Path, dataset_files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in dataset_files:
        try:
            dataset = load_dataset_file(path)
            mappings = load_dataset_mappings(workspace, str(dataset.get("id") or "").strip())
        except MetadataError as exc:
            errors.append(str(exc))
            continue
        findings = completeness_findings(dataset, mappings=mappings)
        for item in findings["should_add_metrics"]:
            errors.append(
                f"{path.name}.fields[{item.get('field')}]: metric-like field is not registered in dataset.metrics; "
                "add a metric or set not_metric_reason"
            )
        for item in findings["mapping_gaps"]:
            errors.append(
                f"{item.get('mapping_id')}.mappings[{item.get('index')}]: metric mapping "
                f"{item.get('view_field')!r} has no matching dataset metric"
            )
        for item in findings["needs_review"]:
            errors.append(f"{path.name}.fields[{item.get('field')}]: {item.get('reason')}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate LLM-native metadata YAML files.")
    parser.add_argument("--workspace", default=None, help="Workspace root. Defaults to discovered RealAnalyst root.")
    parser.add_argument("--completeness", action="store_true", help="Check metric/mapping/sample-profile completeness.")
    parser.add_argument("--strict", action="store_true", help="Alias for --completeness with strict gates.")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    errors: list[str] = []
    warnings: list[str] = []
    dataset_files = list(iter_dataset_files(workspace))
    dictionary_files = list(iter_dictionary_files(workspace))
    mapping_files = list(iter_mapping_files(workspace))
    for path in dataset_files:
        try:
            data = load_dataset_file(path)
            errors.extend(validate_dataset(data, path=path))
            warnings.extend(dataset_size_warnings(path=path))
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
    if args.completeness or args.strict:
        errors.extend(validate_completeness(workspace, dataset_files))

    payload = {
        "success": not errors,
        "workspace": str(workspace),
        "completeness": bool(args.completeness or args.strict),
        "checked_files": [str(path) for path in [*dataset_files, *dictionary_files, *mapping_files]],
        "dataset_count": len(dataset_files),
        "dictionary_count": len(dictionary_files),
        "mapping_count": len(mapping_files),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
