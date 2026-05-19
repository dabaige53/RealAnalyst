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
    "alias": "aliases.jsonl",
}

FTS5_TYPE_MAP = {
    "dataset": "dataset",
    "field": "field",
    "metric": "metric",
    "mapping": "mapping",
    "term": "glossary",
    "alias": "alias",
    "all": "all",
}

ALIAS_ENTITY_TYPES = {
    "field": "field",
    "metric": "metric",
    "term": "glossary",
}


def _json_output(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _selected_types(record_type: str) -> list[str]:
    if record_type == "all":
        return list(INDEX_FILES)
    if record_type in ALIAS_ENTITY_TYPES:
        return [record_type, "alias"]
    return [record_type]


def _fts5_record_types(record_type: str) -> list[str] | None:
    if record_type == "all":
        return None
    base_type = FTS5_TYPE_MAP.get(record_type, record_type)
    if record_type in ALIAS_ENTITY_TYPES:
        return [base_type, "alias"]
    return [base_type]


def _filter_matches(matches: list[dict[str, Any]], record_type: str) -> list[dict[str, Any]]:
    if record_type == "all":
        return matches
    expected = FTS5_TYPE_MAP.get(record_type, record_type)
    alias_entity_type = ALIAS_ENTITY_TYPES.get(record_type)
    filtered: list[dict[str, Any]] = []
    for record in matches:
        if record.get("record_type") == expected:
            filtered.append(record)
        elif record.get("record_type") == "alias" and alias_entity_type and record.get("entity_type") == alias_entity_type:
            filtered.append(record)
    return filtered


def main() -> int:
    parser = argparse.ArgumentParser(description="Search lightweight metadata JSONL indexes.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--index-dir", default=None)
    parser.add_argument("--type", choices=["dataset", "field", "metric", "mapping", "term", "alias", "all"], default="all")
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    index_dir = Path(args.index_dir).expanduser().resolve() if args.index_dir else workspace / "metadata" / "index"

    fts5_db = index_dir / "search.db"
    if fts5_db.exists():
        matches = search_fts5(
            fts5_db,
            args.query,
            record_type=_fts5_record_types(args.type),
            limit=args.limit * 3 if args.type in ALIAS_ENTITY_TYPES else args.limit,
        )
        matches = _filter_matches(matches, args.type)[: args.limit]
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
    matches = _filter_matches(search_records(records, args.query, limit=args.limit * 3), args.type)[: args.limit]

    _json_output(
        {
            "success": True,
            "query": args.query,
            "type": args.type,
            "backend": "jsonl",
            "matches": matches,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
