#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_facts import read_all_dataset_facts, read_dataset_facts  # noqa: E402
from skills.metadata.lib.metadata_io import MetadataError  # noqa: E402


def _emit(payload: dict, *, exit_code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Read exact dataset metadata facts for reports and agents.")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--dataset-id")
    scope.add_argument("--all", action="store_true")
    parser.add_argument("--workspace", default=None)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    try:
        results = read_all_dataset_facts(workspace) if args.all else [read_dataset_facts(workspace, args.dataset_id)]
    except MetadataError as exc:
        return _emit({"success": False, "error": str(exc), "error_code": "METADATA_READ_FAILED"}, exit_code=1)
    return _emit({"success": True, "results": results}, exit_code=0)


if __name__ == "__main__":
    raise SystemExit(main())
