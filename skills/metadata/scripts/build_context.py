#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_context import build_context_pack
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
    parser.add_argument("--dataset-id", required=True, help="Metadata dataset id, for example demo.retail.orders")
    parser.add_argument("--metric", action="append", default=None)
    parser.add_argument("--field", action="append", default=None)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    try:
        path = resolve_dataset_path(workspace, args.dataset_id)
        dataset = normalize_dataset(load_dataset_file(path), path=path)
        dictionaries = [load_mapping_file(path) for path in iter_dictionary_files(workspace)]
        mappings = [load_mapping_file(path) for path in iter_mapping_files(workspace)]
    except MetadataError as exc:
        raise SystemExit(str(exc)) from exc
    context = build_context_pack(dataset, metrics=args.metric, fields=args.field, dictionaries=dictionaries, mappings=mappings)

    print(json.dumps(context, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
