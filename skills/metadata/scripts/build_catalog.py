#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_catalog import build_catalog
from skills.metadata.lib.metadata_io import (
    MetadataError,
    iter_dataset_files,
    load_dataset_file,
    normalize_dataset,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a lightweight dataset catalog summary.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--domain", default=None, help="Filter datasets by business domain.")
    parser.add_argument("--group-by", dest="group_by", choices=["domain"], default=None, help="Group output by field.")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    try:
        datasets = [normalize_dataset(load_dataset_file(path), path=path) for path in iter_dataset_files(workspace)]
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
