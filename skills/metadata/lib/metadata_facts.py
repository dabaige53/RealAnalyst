#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from runtime.tableau import sqlite_store
from skills.metadata.lib.metadata_io import (
    MetadataError,
    iter_dataset_files,
    iter_mapping_files,
    load_dataset_file,
    load_mapping_file,
    normalize_dataset,
    resolve_dataset_path,
)
from skills.metadata.lib.metadata_search import load_jsonl


MISSING = "未维护"
UNREGISTERED = "未注册"


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _list_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in _list(value) if isinstance(item, dict)]


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _index_records(workspace: Path, dataset_id: str) -> dict[str, list[dict[str, Any]]]:
    index_dir = workspace / "metadata" / "index"
    output: dict[str, list[dict[str, Any]]] = {}
    for record_type, filename in {
        "datasets": "datasets.jsonl",
        "fields": "fields.jsonl",
        "metrics": "metrics.jsonl",
        "mappings": "mappings.jsonl",
    }.items():
        records = []
        path = index_dir / filename
        try:
            index_records = load_jsonl(path)
        except json.JSONDecodeError as exc:
            raise MetadataError(f"{path} contains invalid JSONL: {exc}") from exc
        for record in index_records:
            if record.get("dataset_id") == dataset_id or record.get("source_id") == dataset_id:
                records.append(record)
        output[record_type] = records
    return output


def _registry_facts(workspace: Path, dataset_id: str) -> dict[str, Any]:
    old_db_path = sqlite_store._DB_PATH
    sqlite_store._DB_PATH = workspace / "runtime" / "registry.db"
    registry_path = sqlite_store.db_path()
    try:
        if not registry_path.exists():
            return {
                "registry_db": str(registry_path),
                "registered": False,
                "entry": None,
                "spec": None,
                "status": UNREGISTERED,
            }
        entry = sqlite_store.get_entry_by_source_id(dataset_id)
        spec = sqlite_store.load_spec_for_entry(entry) if entry else None
        return {
            "registry_db": str(registry_path),
            "registered": bool(entry),
            "entry": entry,
            "spec": spec,
            "status": "已注册" if entry else UNREGISTERED,
        }
    finally:
        sqlite_store._DB_PATH = old_db_path


def _mapping_matches(workspace: Path, dataset: dict[str, Any]) -> list[dict[str, Any]]:
    dataset_id = _text(dataset.get("id"))
    mapping_ref = _text(dataset.get("mapping_ref"))
    matches: list[dict[str, Any]] = []
    for path in iter_mapping_files(workspace):
        mapping = load_mapping_file(path)
        if _text(mapping.get("id")) == mapping_ref or _text(mapping.get("source_id")) == dataset_id:
            item = dict(mapping)
            item["_metadata_path"] = str(path)
            matches.append(item)
    return matches


def _status(workspace: Path, dataset_id: str, path: Path, registry: dict[str, Any], index_records: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "metadata_yaml": True,
        "metadata_path": str(path),
        "metadata_index": bool(index_records.get("datasets")),
        "runtime_registry": bool(registry.get("entry")),
        "runtime_spec": bool(registry.get("spec")),
        "registry_db": registry.get("registry_db") or str(workspace / "runtime" / "registry.db"),
    }


def read_dataset_facts(workspace: Path, dataset_id: str) -> dict[str, Any]:
    path = resolve_dataset_path(workspace, dataset_id)
    dataset = normalize_dataset(load_dataset_file(path), path=path)
    resolved_id = _text(dataset.get("id"))
    if not resolved_id:
        raise MetadataError(f"{path} is missing required id")
    index_records = _index_records(workspace, resolved_id)
    registry = _registry_facts(workspace, resolved_id)
    return {
        "success": True,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dataset_id": resolved_id,
        "dataset_path": str(path),
        "dataset": dataset,
        "mappings": _mapping_matches(workspace, dataset),
        "index_records": index_records,
        "registry": registry,
        "status": _status(workspace, resolved_id, path, registry, index_records),
    }


def read_all_dataset_facts(workspace: Path) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for path in iter_dataset_files(workspace):
        dataset = load_dataset_file(path)
        dataset_id = _text(dataset.get("id"))
        if dataset_id:
            facts.append(read_dataset_facts(workspace, dataset_id))
    return facts
