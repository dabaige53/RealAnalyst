#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_io import MetadataError, iter_dataset_files, load_dataset_file, normalize_dataset


REQUIRED_DATASET_KEYS = ("version", "id", "display_name", "source", "business", "maintenance", "fields")


def require(mapping: dict[str, Any], key: str, errors: list[str], prefix: str) -> None:
    if key not in mapping or mapping.get(key) in (None, ""):
        errors.append(f"{prefix}.{key} is required")


def validate_definition(definition: dict[str, Any], errors: list[str], prefix: str) -> None:
    for key in ("text", "confidence", "source_evidence", "needs_review"):
        require(definition, key, errors, prefix)
    confidence = definition.get("confidence")
    if isinstance(confidence, (int, float)) and confidence < 0.7 and definition.get("needs_review") is not True:
        errors.append(f"{prefix}: low confidence definitions must set needs_review=true")
    evidence = definition.get("source_evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append(f"{prefix}.source_evidence must contain at least one evidence item")


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
        definition = field.get("business_definition")
        if isinstance(definition, dict):
            validate_definition(definition, errors, f"{prefix}.business_definition")
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
        definition = metric.get("business_definition")
        if isinstance(definition, dict):
            validate_definition(definition, errors, f"{prefix}.business_definition")
        else:
            errors.append(f"{prefix}.business_definition is required")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate LLM-native metadata YAML files.")
    parser.add_argument("--workspace", default=None, help="Workspace root. Defaults to discovered RealAnalyst root.")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    errors: list[str] = []
    files = list(iter_dataset_files(workspace))
    for path in files:
        try:
            errors.extend(validate_dataset(load_dataset_file(path), path=path))
        except MetadataError as exc:
            errors.append(str(exc))

    payload = {
        "success": not errors,
        "workspace": str(workspace),
        "checked_files": [str(path) for path in files],
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
