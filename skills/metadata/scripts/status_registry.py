#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from runtime.tableau.sqlite_store import db_path  # noqa: E402
from skills.metadata.lib.metadata_io import iter_dataset_files, load_dataset_file, resolve_dataset_path  # noqa: E402


def _index_has_dataset(workspace: Path, dataset_id: str) -> bool:
    index_path = workspace / "metadata" / "index" / "datasets.jsonl"
    if not index_path.exists():
        return False
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("dataset_id") == dataset_id:
            return True
    return False


def _load_registry_item(dataset_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, Path | None]:
    registry_path = db_path()
    if not registry_path.exists():
        return None, None, None
    with sqlite3.connect(registry_path) as conn:
        conn.row_factory = sqlite3.Row
        entry_row = conn.execute("SELECT entry_key, payload_json FROM entries WHERE source_id = ? LIMIT 1", (dataset_id,)).fetchone()
        if not entry_row:
            return None, None, registry_path
        entry = json.loads(entry_row["payload_json"])
        spec_row = conn.execute("SELECT spec_json FROM specs WHERE entry_key = ? LIMIT 1", (entry_row["entry_key"],)).fetchone()
        spec = json.loads(spec_row["spec_json"]) if spec_row else None
    return entry, spec, registry_path


def _export_ready(workspace: Path, entry: dict[str, Any] | None, spec: dict[str, Any] | None) -> bool:
    if not entry or not spec:
        return False
    connector = entry.get("source_backend")
    if connector == "duckdb":
        duckdb = entry.get("duckdb") if isinstance(entry.get("duckdb"), dict) else {}
        db_value = duckdb.get("db_path")
        if not db_value or not duckdb.get("object_name") or not spec.get("fields"):
            return False
        db_file = Path(str(db_value)).expanduser()
        if not db_file.is_absolute():
            db_file = workspace / db_file
        return db_file.exists()
    if connector == "tableau":
        tableau = entry.get("tableau") if isinstance(entry.get("tableau"), dict) else {}
        return bool(tableau.get("content_url") or tableau.get("view_luid"))
    return bool(spec.get("fields"))


def _status_for_path(workspace: Path, path: Path) -> dict[str, Any]:
    data = load_dataset_file(path)
    dataset_id = str(data.get("id") or "").strip()
    entry, spec, registry_path = _load_registry_item(dataset_id)
    return {
        "dataset_id": dataset_id,
        "metadata_yaml": True,
        "metadata_path": str(path),
        "metadata_index": _index_has_dataset(workspace, dataset_id),
        "runtime_registry": bool(entry),
        "runtime_spec": bool(spec),
        "export_ready": _export_ready(workspace, entry, spec),
        "registry_db": str(registry_path) if registry_path else str(db_path()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Show metadata/index/runtime registry status for datasets.")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--dataset-id")
    scope.add_argument("--all", action="store_true")
    parser.add_argument("--workspace", default=None)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    paths = list(iter_dataset_files(workspace)) if args.all else [resolve_dataset_path(workspace, args.dataset_id)]
    results = [_status_for_path(workspace, path) for path in paths]
    print(json.dumps({"success": True, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
