#!/usr/bin/env python3
"""Metadata catalog entry point for RA:metadata-search skill.

Thin wrapper around skills.metadata.lib.metadata_catalog.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_catalog import build_catalog
from skills.metadata.lib.metadata_io import MetadataError, iter_dataset_files, load_dataset_file, normalize_dataset


def main() -> int:
    parser = argparse.ArgumentParser(
        description="浏览可用数据集目录摘要（RA:metadata-search catalog）。",
    )
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--domain", default=None, help="按业务域过滤数据集。")
    parser.add_argument(
        "--group-by",
        dest="group_by",
        choices=["domain"],
        default=None,
        help="按字段分组输出。",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR

    try:
        datasets = [
            normalize_dataset(load_dataset_file(path), path=path)
            for path in iter_dataset_files(workspace)
        ]
    except MetadataError as exc:
        raise SystemExit(str(exc)) from exc

    catalog = build_catalog(
        datasets,
        domain=args.domain,
        group_by_domain=(args.group_by == "domain"),
    )
    print(json.dumps(catalog, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
