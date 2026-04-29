#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from _bootstrap import bootstrap_workspace_path


def copy_file(source: Path, target: Path, *, force: bool) -> str:
    if target.exists() and not force:
        return "skipped"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize LLM-native metadata workspace.")
    parser.add_argument("--workspace", default=None, help="Workspace root. Defaults to discovered RealAnalyst root.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing sample files.")
    args = parser.parse_args()

    source_workspace = bootstrap_workspace_path()
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else source_workspace
    files = {
        "metadata/README.md": source_workspace / "metadata" / "README.md",
        "metadata/datasets/demo.retail.orders.yaml": source_workspace
        / "metadata"
        / "datasets"
        / "demo.retail.orders.yaml",
        "metadata/models/demo_retail.yaml": source_workspace / "metadata" / "models" / "demo_retail.yaml",
    }

    created: list[str] = []
    skipped: list[str] = []
    for rel, source in files.items():
        status = copy_file(source, workspace / rel, force=args.force)
        if status == "created":
            created.append(rel)
        else:
            skipped.append(rel)

    print(
        json.dumps(
            {"success": True, "workspace": str(workspace), "created": created, "skipped": skipped},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
