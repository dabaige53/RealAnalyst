#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_context import build_context_pack, build_multi_context_pack
from skills.metadata.lib.metadata_io import (
    MetadataError,
    iter_dictionary_files,
    iter_mapping_files,
    load_dataset_file,
    load_mapping_file,
    normalize_dataset,
    resolve_dataset_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a small metadata context pack from layered metadata YAML.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--dataset-id", action="append", required=True, help="Metadata dataset id (repeatable for multi-dataset context)")
    parser.add_argument("--metric", action="append", default=None)
    parser.add_argument("--field", action="append", default=None)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    try:
        datasets = [
            normalize_dataset(load_dataset_file(resolve_dataset_path(workspace, did)), path=resolve_dataset_path(workspace, did))
            for did in args.dataset_id
        ]
        dictionaries = [load_mapping_file(p) for p in iter_dictionary_files(workspace)]
        mappings = [load_mapping_file(p) for p in iter_mapping_files(workspace)]
    except MetadataError as exc:
        raise SystemExit(str(exc)) from exc

    if len(datasets) == 1:
        context = build_context_pack(datasets[0], metrics=args.metric, fields=args.field, dictionaries=dictionaries, mappings=mappings)
    else:
        context = build_multi_context_pack(datasets, metrics=args.metric, fields=args.field, dictionaries=dictionaries, mappings=mappings)

    print(json.dumps(context, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
