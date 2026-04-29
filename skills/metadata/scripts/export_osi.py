#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_io import iter_dataset_files, load_dataset_file, normalize_dataset
from skills.metadata.lib.metadata_osi import build_osi_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Export metadata YAML into OSI semantic model YAML.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else workspace / "metadata" / "osi" / f"{args.model_name}.osi.yaml"
    )

    datasets = [normalize_dataset(load_dataset_file(path), path=path) for path in iter_dataset_files(workspace)]
    payload = build_osi_model(args.model_name, datasets)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "success": True,
                "model_name": args.model_name,
                "output": str(output_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
