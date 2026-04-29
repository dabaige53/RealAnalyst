#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


class MetadataError(ValueError):
    """Raised when metadata YAML cannot be loaded or normalized."""


@dataclass(frozen=True)
class MetadataPaths:
    workspace: Path

    @property
    def metadata_dir(self) -> Path:
        return self.workspace / "metadata"

    @property
    def datasets_dir(self) -> Path:
        return self.metadata_dir / "datasets"

    @property
    def models_dir(self) -> Path:
        return self.metadata_dir / "models"


def dataset_path_for_id(workspace: Path, dataset_id: str) -> Path:
    if not dataset_id or "/" in dataset_id:
        raise MetadataError(f"Invalid dataset id: {dataset_id!r}")
    return MetadataPaths(workspace).datasets_dir / f"{dataset_id}.yaml"


def _source_reference_candidates(data: dict[str, Any]) -> set[str]:
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    candidates = {
        str(data.get("id") or "").strip(),
        str(data.get("source_id") or "").strip(),
        str(source.get("id") or "").strip(),
        str(source.get("source_id") or "").strip(),
        str(source.get("object") or "").strip(),
    }
    connector = str(source.get("connector") or "").strip()
    for nested_key in ("duckdb", "tableau"):
        nested = source.get(nested_key) if isinstance(source.get(nested_key), dict) else {}
        object_name = str(nested.get("object_name") or "").strip()
        candidates.update(
            {
                str(nested.get("id") or "").strip(),
                str(nested.get("source_id") or "").strip(),
                object_name,
            }
        )
        if connector and object_name:
            candidates.add(f"{connector}.{object_name}")
            candidates.add(f"{connector}.example.{object_name}")
    return {item for item in candidates if item}


def resolve_dataset_path(workspace: Path, dataset_ref: str) -> Path:
    direct_path = dataset_path_for_id(workspace, dataset_ref)
    if direct_path.exists():
        return direct_path

    matches: list[Path] = []
    suffix_matches: list[Path] = []
    for path in iter_dataset_files(workspace):
        data = load_dataset_file(path)
        candidates = _source_reference_candidates(data)
        if dataset_ref in candidates:
            matches.append(path)
            continue
        source = data.get("source") if isinstance(data.get("source"), dict) else {}
        duckdb = source.get("duckdb") if isinstance(source.get("duckdb"), dict) else {}
        object_name = str(duckdb.get("object_name") or "").strip()
        if object_name and dataset_ref.endswith(f".{object_name}"):
            suffix_matches.append(path)

    resolved = matches or suffix_matches
    if len(resolved) == 1:
        return resolved[0]
    if len(resolved) > 1:
        names = ", ".join(path.name for path in resolved)
        raise MetadataError(f"Ambiguous dataset reference {dataset_ref!r}: {names}")
    raise MetadataError(f"No metadata dataset found for {dataset_ref!r}")


def iter_dataset_files(workspace: Path) -> Iterable[Path]:
    datasets_dir = MetadataPaths(workspace).datasets_dir
    if not datasets_dir.exists():
        return []
    return sorted(path for path in datasets_dir.glob("*.yaml") if path.is_file())


def load_yaml_file(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise MetadataError(f"Invalid YAML in {path}: {exc}") from exc


def load_dataset_file(path: Path) -> dict[str, Any]:
    data = load_yaml_file(path)
    if not isinstance(data, dict):
        raise MetadataError(f"{path} must contain a mapping")
    return data


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_dataset(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    dataset = dict(data)
    dataset_id = str(dataset.get("id") or "").strip()
    if not dataset_id:
        label = str(path) if path else "dataset"
        raise MetadataError(f"{label} is missing required id")

    dataset["source_id"] = dataset_id
    dataset["fields"] = _as_list(dataset.get("fields"))
    dataset["metrics"] = _as_list(dataset.get("metrics"))
    dataset["relationships"] = _as_list(dataset.get("relationships"))

    business = dataset.get("business") if isinstance(dataset.get("business"), dict) else {}
    for key in ("grain", "primary_key", "time_fields", "suitable_for", "not_suitable_for", "sample_questions"):
        business[key] = _as_list(business.get(key))
    dataset["business"] = business

    maintenance = dataset.get("maintenance") if isinstance(dataset.get("maintenance"), dict) else {}
    maintenance["pending_questions"] = _as_list(maintenance.get("pending_questions"))
    dataset["maintenance"] = maintenance
    return dataset
