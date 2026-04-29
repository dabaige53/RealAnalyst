#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_index import build_all_indexes, write_jsonl
from skills.metadata.lib.metadata_io import iter_dataset_files, load_dataset_file, normalize_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Build lightweight metadata indexes from LLM-maintained YAML.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else workspace / "metadata" / "index"

    datasets = [normalize_dataset(load_dataset_file(path), path=path) for path in iter_dataset_files(workspace)]
    indexes = build_all_indexes(datasets)
    for name, records in indexes.items():
        write_jsonl(output_dir / f"{name}.jsonl", records)

    print(
        json.dumps(
            {
                "success": True,
                "dataset_count": len(datasets),
                "output_dir": str(output_dir),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
