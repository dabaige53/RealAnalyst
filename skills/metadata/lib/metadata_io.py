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
    def dictionaries_dir(self) -> Path:
        return self.metadata_dir / "dictionaries"

    @property
    def mappings_dir(self) -> Path:
        return self.metadata_dir / "mappings"

    @property
    def models_dir(self) -> Path:
        return self.metadata_dir / "models"


def dataset_path_for_id(workspace: Path, dataset_id: str) -> Path:
    if not dataset_id or "/" in dataset_id:
        raise MetadataError(f"Invalid dataset id: {dataset_id!r}")
    return MetadataPaths(workspace).datasets_dir / f"{dataset_id}.yaml"


def resolve_dataset_path(workspace: Path, dataset_id: str) -> Path:
    direct_path = dataset_path_for_id(workspace, dataset_id)
    if direct_path.exists():
        return direct_path

    matches: list[Path] = []
    for path in iter_dataset_files(workspace):
        data = load_dataset_file(path)
        if str(data.get("id") or "").strip() == dataset_id:
            matches.append(path)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches)
        raise MetadataError(f"Ambiguous dataset id {dataset_id!r}: {names}")
    raise MetadataError(f"No metadata dataset found for id {dataset_id!r}")


def iter_dataset_files(workspace: Path) -> Iterable[Path]:
    return iter_yaml_files(MetadataPaths(workspace).datasets_dir)


def iter_dictionary_files(workspace: Path) -> Iterable[Path]:
    return iter_yaml_files(MetadataPaths(workspace).dictionaries_dir)


def iter_mapping_files(workspace: Path) -> Iterable[Path]:
    return iter_yaml_files(MetadataPaths(workspace).mappings_dir)


def iter_yaml_files(directory: Path) -> Iterable[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.glob("*.yaml") if path.is_file())


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


def load_mapping_file(path: Path) -> dict[str, Any]:
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
