from __future__ import annotations

import json
from pathlib import Path
from typing import Any


INVENTORY_ROOTS = ("metadata", "schemas", "scripts", "skills", "docs")


def is_inventory_file(path: Path) -> bool:
    return path.is_file() and "__pycache__" not in path.parts and not any(part.startswith(".") for part in path.parts)


def classify_path(path: Path) -> str:
    rel = path.as_posix()
    suffix = path.suffix.lower()

    if rel.startswith("metadata/sources/"):
        return "metadata_evidence"
    if rel.startswith("metadata/dictionaries/"):
        return "metadata_dictionary" if suffix in {".yaml", ".yml"} else "metadata_dictionary_doc"
    if rel.startswith("metadata/mappings/"):
        return "metadata_mapping" if suffix in {".yaml", ".yml"} else "metadata_mapping_doc"
    if rel.startswith("metadata/datasets/") and suffix in {".yaml", ".yml"}:
        return "metadata_dataset"
    if rel.startswith("metadata/models/") and suffix in {".yaml", ".yml"}:
        return "semantic_model"
    if rel.startswith("metadata/index/") and suffix == ".jsonl":
        return "generated_index"
    if rel.startswith("metadata/conversion/") and suffix in {".yaml", ".yml"}:
        return "conversion_manifest"
    if rel.startswith("schemas/"):
        return "schema"
    if rel.startswith("skills/metadata/lib/") and suffix == ".py":
        return "metadata_library"
    if rel.startswith("skills/metadata/adapters/"):
        return "connector_adapter"
    if rel.startswith("skills/"):
        return "skill"
    if rel.startswith("docs/"):
        return "documentation"
    return "other"


def iter_inventory_files(workspace: Path) -> list[Path]:
    paths: list[Path] = []
    for root_name in INVENTORY_ROOTS:
        root = workspace / root_name
        if not root.exists():
            continue
        paths.extend(path.relative_to(workspace) for path in root.rglob("*") if is_inventory_file(path))
    return sorted(paths)


def build_inventory(workspace: Path) -> dict[str, Any]:
    files = []
    summary: dict[str, int] = {}
    for path in iter_inventory_files(workspace):
        role = classify_path(path)
        files.append({"path": path.as_posix(), "role": role})
        summary[role] = summary.get(role, 0) + 1
    return {"version": "0.1", "files": files, "summary": summary}


def write_inventory_json(path: Path, inventory: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
