#!/usr/bin/env python3
"""Metadata search entry point for RA:metadata-search skill.

Thin wrapper around skills.metadata.lib.metadata_search.
Supports: metric / field / term / dataset / mapping / all
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

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


def _selected_types(record_type: str) -> list[str]:
    if record_type == "all":
        return list(INDEX_FILES)
    return [record_type]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="搜索 metadata index（RA:metadata-search）。",
        epilog="支持类型：metric / field / term / dataset / mapping / all",
    )
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--index-dir", default=None)
    parser.add_argument(
        "--type",
        choices=["dataset", "field", "metric", "mapping", "term", "all"],
        default="all",
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    index_dir = (
        Path(args.index_dir).expanduser().resolve()
        if args.index_dir
        else workspace / "metadata" / "index"
    )

    fts5_db = index_dir / "search.db"
    if fts5_db.exists():
        fts5_type = FTS5_TYPE_MAP.get(args.type, args.type)
        matches = search_fts5(
            fts5_db,
            args.query,
            record_type=fts5_type if fts5_type != "all" else None,
            limit=args.limit,
        )
        print(
            json.dumps(
                {"success": True, "query": args.query, "type": args.type, "backend": "fts5", "matches": matches},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    missing = [
        INDEX_FILES[t]
        for t in _selected_types(args.type)
        if not (index_dir / INDEX_FILES[t]).exists()
    ]
    if missing:
        print(
            json.dumps(
                {
                    "success": False,
                    "query": args.query,
                    "type": args.type,
                    "matches": [],
                    "message": "Index file missing. Run: python3 skills/metadata/scripts/metadata.py index",
                    "missing": missing,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1

    records: list[dict] = []
    for t in _selected_types(args.type):
        records.extend(load_jsonl(index_dir / INDEX_FILES[t]))

    print(
        json.dumps(
            {
                "success": True,
                "query": args.query,
                "type": args.type,
                "backend": "jsonl",
                "matches": search_records(records, args.query, limit=args.limit),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
