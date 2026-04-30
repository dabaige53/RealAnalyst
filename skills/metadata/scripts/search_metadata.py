#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_search import load_jsonl, search_fts5, search_records


INDEX_FILES = {
    "dataset": "datasets.jsonl",
    "field": "fields.jsonl",
    "metric": "metrics.jsonl",
    "mapping": "mappings.jsonl",
    "term": "glossary.jsonl",
}

FTS5_TYPE_MAP = {
    "dataset": "dataset",
    "field": "field",
    "metric": "metric",
    "mapping": "mapping",
    "term": "glossary",
    "all": "all",
}


def _json_output(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _selected_types(record_type: str) -> list[str]:
    if record_type == "all":
        return list(INDEX_FILES)
    return [record_type]


def main() -> int:
    parser = argparse.ArgumentParser(description="Search lightweight metadata JSONL indexes.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--index-dir", default=None)
    parser.add_argument("--type", choices=["dataset", "field", "metric", "mapping", "term", "all"], default="all")
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    index_dir = Path(args.index_dir).expanduser().resolve() if args.index_dir else workspace / "metadata" / "index"

    fts5_db = index_dir / "search.db"
    if fts5_db.exists():
        fts5_record_type = FTS5_TYPE_MAP.get(args.type, args.type)
        matches = search_fts5(
            fts5_db,
            args.query,
            record_type=fts5_record_type if fts5_record_type != "all" else None,
            limit=args.limit,
        )
        _json_output(
            {
                "success": True,
                "query": args.query,
                "type": args.type,
                "backend": "fts5",
                "matches": matches,
            }
        )
        return 0

    missing = [
        INDEX_FILES[record_type]
        for record_type in _selected_types(args.type)
        if not (index_dir / INDEX_FILES[record_type]).exists()
    ]
    if missing:
        _json_output(
            {
                "success": False,
                "query": args.query,
                "type": args.type,
                "matches": [],
                "message": "Index file missing. Run metadata index first.",
                "missing": missing,
            }
        )
        return 1

    records: list[dict[str, Any]] = []
    for record_type in _selected_types(args.type):
        records.extend(load_jsonl(index_dir / INDEX_FILES[record_type]))

    _json_output(
        {
            "success": True,
            "query": args.query,
            "type": args.type,
            "backend": "jsonl",
            "matches": search_records(records, args.query, limit=args.limit),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
