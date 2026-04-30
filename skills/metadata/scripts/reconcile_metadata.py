#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIR = bootstrap_workspace_path()

from runtime.runtime_config_store import db_path as runtime_db_path, ensure_store_ready as ensure_runtime_ready  # noqa: E402
from skills.metadata.lib.metadata_io import (
    MetadataError,
    iter_dataset_files,
    iter_dictionary_files,
    load_dataset_file,
    load_mapping_file,
    normalize_dataset,
)
from skills.metadata.lib.metadata_reconcile import reconcile


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile runtime registry lookup tables vs metadata YAML.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--runtime-db", default=None, help="Path to runtime SQLite DB. Defaults to runtime/registry.db.")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR

    runtime_db = Path(args.runtime_db).expanduser().resolve() if args.runtime_db else runtime_db_path()
    ensure_runtime_ready()

    try:
        datasets = [normalize_dataset(load_dataset_file(path), path=path) for path in iter_dataset_files(workspace)]
        dictionaries = [load_mapping_file(path) for path in iter_dictionary_files(workspace)]
    except MetadataError as exc:
        raise SystemExit(str(exc)) from exc

    result = reconcile(runtime_db, datasets, dictionaries)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
