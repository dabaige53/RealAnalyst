#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_context import build_context_pack
from skills.metadata.lib.metadata_io import MetadataError, load_dataset_file, normalize_dataset, resolve_dataset_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a small metadata context pack from dataset YAML.")
    parser.add_argument("--workspace", default=None)
    ref = parser.add_mutually_exclusive_group(required=True)
    ref.add_argument("--dataset-id", dest="dataset_ref", help="Metadata dataset id, for example demo.retail.orders")
    ref.add_argument("--source-id", dest="dataset_ref", help="Backward-compatible alias for dataset/source references")
    parser.add_argument("--metric", action="append", default=None)
    parser.add_argument("--field", action="append", default=None)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    try:
        path = resolve_dataset_path(workspace, args.dataset_ref)
        dataset = normalize_dataset(load_dataset_file(path), path=path)
    except MetadataError as exc:
        raise SystemExit(str(exc)) from exc
    context = build_context_pack(dataset, metrics=args.metric, fields=args.field)

    print(json.dumps(context, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
