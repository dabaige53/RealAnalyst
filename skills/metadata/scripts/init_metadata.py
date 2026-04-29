#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIRS = (
    "metadata/sources",
    "metadata/dictionaries",
    "metadata/mappings",
    "metadata/datasets",
    "metadata/models",
    "metadata/sync/duckdb",
    "metadata/sync/tableau",
    "metadata/index",
    "metadata/osi",
)
CLEAN_FILES = {
    "metadata/README.md": "metadata/README.md",
    "metadata/sources/README.md": "metadata/sources/README.md",
    "metadata/dictionaries/README.md": "metadata/dictionaries/README.md",
    "metadata/mappings/README.md": "metadata/mappings/README.md",
    "metadata/datasets/README.md": "metadata/datasets/README.md",
    "metadata/models/README.md": "metadata/models/README.md",
    "metadata/sync/README.md": "metadata/sync/README.md",
    "metadata/sync/duckdb/README.md": "metadata/sync/duckdb/README.md",
    "metadata/sync/tableau/README.md": "metadata/sync/tableau/README.md",
    "metadata/conversion/README.md": "metadata/conversion/README.md",
    "metadata/conversion/metadata_conversion_manifest.yaml": "metadata/conversion/metadata_conversion_manifest.yaml",
}
DEMO_FILES = {
    "metadata/datasets/demo.retail.orders.yaml": "metadata/datasets/demo.retail.orders.yaml",
    "metadata/models/demo_retail.yaml": "metadata/models/demo_retail.yaml",
}
FALLBACK_FILE_CONTENTS = {
    "metadata/README.md": "# Metadata\n\nMaintain dataset fields, metrics, business definitions, evidence, and open questions here.\n",
    "metadata/sources/README.md": "# Sources\n\nArchive source materials here before extracting dictionaries, mappings, or datasets.\n",
    "metadata/dictionaries/README.md": "# Dictionaries\n\nMaintain shared metrics, dimensions, and glossary YAML here. These files are not datasets.\n",
    "metadata/mappings/README.md": "# Mappings\n\nMaintain source-field to standard semantic mappings here.\n",
    "metadata/datasets/README.md": "# Datasets\n\nCreate one YAML file per registered dataset.\n",
    "metadata/models/README.md": "# Models\n\nGroup related datasets into business domains or semantic models.\n",
    "metadata/sync/README.md": "# Sync\n\nStore connector discovery snapshots here only after the user asks to sync a source.\n",
    "metadata/sync/duckdb/README.md": "# DuckDB Sync\n\nDuckDB discovery snapshots go here.\n",
    "metadata/sync/tableau/README.md": "# Tableau Sync\n\nTableau field, filter, and workbook snapshots go here.\n",
    "metadata/conversion/README.md": "# Conversion\n\nMetadata conversion notes and manifests go here.\n",
    "metadata/conversion/metadata_conversion_manifest.yaml": "version: 1\nconversions: []\n",
}


def copy_file(source: Path, target: Path, *, fallback: str | None, force: bool) -> str:
    if target.exists() and not force:
        return "skipped"
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        shutil.copyfile(source, target)
    elif fallback is not None:
        target.write_text(fallback, encoding="utf-8")
    else:
        raise FileNotFoundError(source)
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize LLM-native metadata workspace.")
    parser.add_argument("--workspace", default=None, help="Workspace root. Defaults to discovered RealAnalyst root.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing scaffold files.")
    parser.add_argument("--with-demo", action="store_true", help="Also copy demo metadata files.")
    args = parser.parse_args()

    source_workspace = bootstrap_workspace_path()
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else source_workspace
    files = {rel: source_workspace / source_rel for rel, source_rel in CLEAN_FILES.items()}
    if args.with_demo:
        files.update({rel: source_workspace / source_rel for rel, source_rel in DEMO_FILES.items()})

    directories: list[str] = []
    for rel in WORKSPACE_DIRS:
        path = workspace / rel
        path.mkdir(parents=True, exist_ok=True)
        directories.append(rel)

    created: list[str] = []
    skipped: list[str] = []
    for rel, source in files.items():
        status = copy_file(source, workspace / rel, fallback=FALLBACK_FILE_CONTENTS.get(rel, ""), force=args.force)
        if status == "created":
            created.append(rel)
        else:
            skipped.append(rel)

    print(
        json.dumps(
            {
                "success": True,
                "workspace": str(workspace),
                "directories": directories,
                "created": created,
                "skipped": skipped,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
