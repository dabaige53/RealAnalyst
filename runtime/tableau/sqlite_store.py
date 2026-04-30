#!/usr/bin/env python3
"""SQLite-backed unified runtime registry/spec store."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

_WORKSPACE_DIR = Path(__file__).resolve().parents[2]
if str(_WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_DIR))

from runtime.paths import (  # noqa: E402
    runtime_db_path,
    runtime_dir as _runtime_dir,
    workspace_dir as _workspace_dir,
)

_DB_PATH = runtime_db_path()


def workspace_dir() -> Path:
    return _workspace_dir()


def runtime_dir() -> Path:
    return _runtime_dir()


def db_path() -> Path:
    return _DB_PATH


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=False)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            category_key TEXT PRIMARY KEY,
            display_name TEXT,
            entry_keys_json TEXT NOT NULL DEFAULT '[]',
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS entries (
            entry_key TEXT PRIMARY KEY,
            source_id TEXT,
            type TEXT,
            display_name TEXT,
            status TEXT,
            category TEXT,
            filters_ref TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_entries_source_id ON entries(source_id);
        CREATE INDEX IF NOT EXISTS idx_entries_category ON entries(category);
        CREATE INDEX IF NOT EXISTS idx_entries_status ON entries(status);

        CREATE TABLE IF NOT EXISTS specs (
            entry_key TEXT PRIMARY KEY,
            display_name TEXT,
            updated TEXT,
            spec_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS enums (
            enum_ref TEXT PRIMARY KEY,
            enum_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS source_groups (
            group_id TEXT PRIMARY KEY,
            display_name TEXT,
            primary_source_id TEXT NOT NULL,
            member_sources_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            use_count INTEGER NOT NULL DEFAULT 1,
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_sg_primary ON source_groups(primary_source_id);
        """
    )
    conn.commit()


def migrate_from_yaml(*, force: bool = False) -> dict[str, int]:
    ensure_store_ready(force_migrate=False)
    return {"db_path": str(_DB_PATH), "note": "runtime registry is SQLite-only"}


def migrate_specs_enums_from_yaml(*, force: bool = False) -> dict[str, int]:
    ensure_store_ready(force_migrate=False)
    return {"db_path": str(_DB_PATH), "note": "runtime specs/enums are SQLite-only"}


def ensure_store_ready(*, force_migrate: bool = False) -> Path:
    with _connect():
        pass
    return _DB_PATH


def _load_categories(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT category_key, display_name, entry_keys_json FROM categories ORDER BY sort_order, category_key"
    ).fetchall()
    if rows:
        out: dict[str, Any] = {}
        for row in rows:
            out[str(row["category_key"])] = {
                "display_name": row["display_name"],
                "entries": _json_loads(row["entry_keys_json"], []),
            }
        return out

    # Fallback: derive from entries when explicit categories are absent.
    out = {}
    entry_rows = conn.execute(
        "SELECT category, entry_key FROM entries ORDER BY sort_order, entry_key"
    ).fetchall()
    for row in entry_rows:
        category = row["category"]
        if not category:
            continue
        category = str(category)
        bucket = out.setdefault(category, {"display_name": category, "entries": []})
        bucket["entries"].append(row["entry_key"])
    return out


def load_registry_document() -> dict[str, Any]:
    ensure_store_ready()
    with _connect() as conn:
        metadata_rows = conn.execute("SELECT key, value_json FROM metadata").fetchall()
        meta = {str(row["key"]): _json_loads(row["value_json"], None) for row in metadata_rows}
        entry_rows = conn.execute(
            "SELECT payload_json FROM entries ORDER BY sort_order, entry_key"
        ).fetchall()
        entries = [_json_loads(row["payload_json"], {}) for row in entry_rows]
        category_index = _load_categories(conn)

    document = {
        "version": meta.get("version") or "1.1",
        "updated": meta.get("updated"),
        "last_verified": meta.get("last_verified"),
        "defaults": meta.get("defaults") or {},
        "entries": entries,
        "category_index": category_index,
    }
    return document


def save_registry_document(document: dict[str, Any]) -> None:
    ensure_store_ready()
    entries = document.get("entries") or []
    category_index = document.get("category_index") or {}
    if not isinstance(entries, list):
        raise ValueError("registry document entries must be a list")
    if not isinstance(category_index, dict):
        raise ValueError("registry document category_index must be a dict")

    with _connect() as conn:
        conn.execute("DELETE FROM metadata")
        conn.execute("DELETE FROM categories")
        conn.execute("DELETE FROM entries")

        for key in ("version", "updated", "last_verified", "defaults"):
            if key in document:
                conn.execute(
                    "INSERT OR REPLACE INTO metadata(key, value_json) VALUES (?, ?)",
                    (key, _json_dumps(document.get(key))),
                )

        for index, (category_key, payload) in enumerate(category_index.items()):
            payload = payload if isinstance(payload, dict) else {}
            conn.execute(
                """
                INSERT INTO categories(category_key, display_name, entry_keys_json, sort_order)
                VALUES (?, ?, ?, ?)
                """,
                (
                    category_key,
                    payload.get("display_name"),
                    _json_dumps(payload.get("entries") or payload.get("sources") or []),
                    index,
                ),
            )

        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            conn.execute(
                """
                INSERT INTO entries(
                    entry_key, source_id, type, display_name, status, category, filters_ref, sort_order, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.get("key"),
                    entry.get("source_id"),
                    entry.get("type"),
                    entry.get("display_name"),
                    entry.get("status"),
                    entry.get("category"),
                    get_filters_ref_for_entry(entry),
                    index,
                    _json_dumps(entry),
                ),
            )

        conn.commit()


def list_entries(*, active_only: bool = False) -> list[dict[str, Any]]:
    document = load_registry_document()
    entries = [e for e in document.get("entries", []) if isinstance(e, dict)]
    if active_only:
        entries = [e for e in entries if e.get("status") == "active"]
    return entries


def get_entry_by_source_id(source_id: str) -> dict[str, Any] | None:
    ensure_store_ready()
    with _connect() as conn:
        row = conn.execute(
            "SELECT payload_json FROM entries WHERE source_id = ? LIMIT 1", (source_id,)
        ).fetchone()
    if not row:
        return None
    return _json_loads(row["payload_json"], {})


def get_entry_by_key(entry_key: str) -> dict[str, Any] | None:
    ensure_store_ready()
    with _connect() as conn:
        row = conn.execute(
            "SELECT payload_json FROM entries WHERE entry_key = ? LIMIT 1", (entry_key,)
        ).fetchone()
    if not row:
        return None
    return _json_loads(row["payload_json"], {})


def get_entry_by_view_luid(view_luid: str) -> dict[str, Any] | None:
    for entry in list_entries(active_only=False):
        tableau = entry.get("tableau")
        if isinstance(tableau, dict) and tableau.get("view_luid") == view_luid:
            return entry
        views = entry.get("views")
        if isinstance(views, list):
            for view in views:
                if isinstance(view, dict) and view.get("view_luid") == view_luid:
                    return entry
    return None


def save_entry(entry: dict[str, Any]) -> None:
    document = load_registry_document()
    entries = [e for e in document.get("entries", []) if isinstance(e, dict)]
    key = entry.get("key")
    if not isinstance(key, str) or not key:
        raise ValueError("entry.key is required")

    replaced = False
    for index, current in enumerate(entries):
        if current.get("key") == key:
            entries[index] = entry
            replaced = True
            break
    if not replaced:
        entries.append(entry)

    document["entries"] = entries

    category = entry.get("category")
    category_index = document.get("category_index")
    if not isinstance(category_index, dict):
        category_index = {}
    if isinstance(category, str) and category:
        bucket = category_index.setdefault(category, {"display_name": category, "entries": []})
        if not isinstance(bucket, dict):
            bucket = {"display_name": category, "entries": []}
            category_index[category] = bucket
        if not isinstance(bucket.get("entries"), list):
            bucket["entries"] = []
        if key not in bucket["entries"]:
            bucket["entries"].append(key)
    document["category_index"] = category_index
    save_registry_document(document)


def _spec_path_to_entry_key(spec_ref: str) -> str:
    """Best-effort legacy fallback only.

    New code should prefer an exact lookup through entries.filters_ref, because
    safe filenames like `sales_ai_.yaml` cannot be losslessly reversed back to
    `sales.ai_` by simple string replacement.
    """
    name = Path(spec_ref).stem
    return name.replace("_", ".")


def get_filters_ref_for_entry(entry: dict[str, Any] | None) -> str | None:
    """Return the stored spec ref for an entry when present."""
    if not isinstance(entry, dict):
        return None
    value = entry.get("filters_ref")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def load_spec_for_entry(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    entry_key = entry.get("key")
    if isinstance(entry_key, str) and entry_key.strip():
        spec = load_spec_by_entry_key(entry_key.strip())
        if isinstance(spec, dict):
            return spec
    filters_ref = get_filters_ref_for_entry(entry)
    if isinstance(filters_ref, str) and filters_ref:
        return load_spec_by_ref(filters_ref)
    return None


def load_spec_by_entry_key(entry_key: str) -> dict[str, Any] | None:
    ensure_store_ready()
    with _connect() as conn:
        row = conn.execute(
            "SELECT spec_json FROM specs WHERE entry_key = ? LIMIT 1", (entry_key,)
        ).fetchone()
    if row:
        return _json_loads(row["spec_json"], {})

    entry = get_entry_by_key(entry_key)
    if not entry:
        return None
    filters_ref = get_filters_ref_for_entry(entry)
    if isinstance(filters_ref, str) and filters_ref:
        return load_spec_by_ref(filters_ref)
    return None


def load_spec_by_ref(spec_ref: str) -> dict[str, Any] | None:
    ensure_store_ready()
    with _connect() as conn:
        entry_row = conn.execute(
            "SELECT entry_key FROM entries WHERE filters_ref = ? LIMIT 1", (spec_ref,)
        ).fetchone()
        if entry_row:
            row = conn.execute(
                "SELECT spec_json FROM specs WHERE entry_key = ? LIMIT 1",
                (entry_row["entry_key"],),
            ).fetchone()
            if row:
                return _json_loads(row["spec_json"], {})

        # Legacy best-effort fallback for older callers/spec refs.
        entry_key = _spec_path_to_entry_key(spec_ref)
        row = conn.execute(
            "SELECT spec_json FROM specs WHERE entry_key = ? LIMIT 1", (entry_key,)
        ).fetchone()
    if not row:
        return None
    return _json_loads(row["spec_json"], {})


def save_spec(spec: dict[str, Any]) -> None:
    ensure_store_ready()
    entry_key = spec.get("entry_key")
    if not isinstance(entry_key, str) or not entry_key:
        raise ValueError("spec.entry_key is required")
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO specs(entry_key, display_name, updated, spec_json) VALUES (?, ?, ?, ?)",
            (
                entry_key,
                spec.get("display_name"),
                spec.get("updated"),
                _json_dumps(spec),
            ),
        )
        conn.commit()


def load_enum_payload(enum_ref: str) -> Any | None:
    ensure_store_ready()
    with _connect() as conn:
        row = conn.execute(
            "SELECT enum_json FROM enums WHERE enum_ref = ? LIMIT 1", (enum_ref,)
        ).fetchone()
    if row:
        return _json_loads(row["enum_json"], None)

    # Backward-compatible fallback: when caller passes bare filename, try enums/<name>.yaml.
    if not enum_ref.startswith("enums/"):
        return load_enum_payload(f"enums/{Path(enum_ref).name}")
    return None


def save_enum_payload(enum_ref: str, payload: Any) -> None:
    ensure_store_ready()
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO enums(enum_ref, enum_json) VALUES (?, ?)",
            (enum_ref, _json_dumps(payload)),
        )
        conn.commit()


def load_allowed_values(enum_ref: str) -> list[str] | None:
    payload = load_enum_payload(enum_ref)
    if isinstance(payload, dict) and isinstance(payload.get("values"), list):
        return [str(x) for x in payload["values"]]
    if isinstance(payload, list):
        return [str(x) for x in payload]
    return None


def normalize_allowed_value(enum_ref: str, value: str) -> str:
    payload = load_enum_payload(enum_ref)
    raw = str(value).strip()
    if not raw:
        return raw
    if isinstance(payload, dict):
        aliases = payload.get("aliases")
        if isinstance(aliases, dict):
            canonical = aliases.get(raw)
            if isinstance(canonical, str) and canonical.strip():
                return canonical.strip()
    return raw


# ---------------------------------------------------------------------------
# Source Groups
# ---------------------------------------------------------------------------

def save_source_group(group: dict[str, Any]) -> None:
    """Upsert a source group into registry.db."""
    ensure_store_ready()
    group_id = group.get("group_id")
    if not isinstance(group_id, str) or not group_id.strip():
        raise ValueError("group.group_id is required")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO source_groups(group_id, display_name, primary_source_id, member_sources_json, created_at, last_used_at, use_count, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(group_id) DO UPDATE SET
                display_name = excluded.display_name,
                primary_source_id = excluded.primary_source_id,
                member_sources_json = excluded.member_sources_json,
                last_used_at = excluded.last_used_at,
                use_count = excluded.use_count,
                notes = excluded.notes
            """,
            (
                group_id,
                group.get("display_name"),
                group.get("primary_source_id", ""),
                _json_dumps(group.get("member_sources") or []),
                group.get("created_at", ""),
                group.get("last_used_at"),
                group.get("use_count", 1),
                group.get("notes"),
            ),
        )
        conn.commit()


def find_groups_by_source(source_id: str) -> list[dict[str, Any]]:
    """Return all source groups that contain *source_id* as any member."""
    ensure_store_ready()
    results: list[dict[str, Any]] = []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT group_id, display_name, primary_source_id, member_sources_json, created_at, last_used_at, use_count, notes FROM source_groups"
        ).fetchall()
    for row in rows:
        members = _json_loads(row["member_sources_json"], [])
        member_ids = [m.get("source_id") if isinstance(m, dict) else str(m) for m in members]
        if source_id in member_ids or row["primary_source_id"] == source_id:
            results.append({
                "group_id": row["group_id"],
                "display_name": row["display_name"],
                "primary_source_id": row["primary_source_id"],
                "member_sources": members,
                "created_at": row["created_at"],
                "last_used_at": row["last_used_at"],
                "use_count": row["use_count"],
                "notes": row["notes"],
            })
    return results


def touch_source_group(group_id: str) -> None:
    """Increment use_count and update last_used_at for an existing group."""
    from datetime import datetime, timezone

    ensure_store_ready()
    now = datetime.now(timezone.utc).astimezone().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE source_groups SET use_count = use_count + 1, last_used_at = ? WHERE group_id = ?",
            (now, group_id),
        )
        conn.commit()


def list_source_groups() -> list[dict[str, Any]]:
    """Return all known source groups ordered by last_used_at descending."""
    ensure_store_ready()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT group_id, display_name, primary_source_id, member_sources_json, created_at, last_used_at, use_count, notes "
            "FROM source_groups ORDER BY last_used_at DESC, use_count DESC"
        ).fetchall()
    return [
        {
            "group_id": row["group_id"],
            "display_name": row["display_name"],
            "primary_source_id": row["primary_source_id"],
            "member_sources": _json_loads(row["member_sources_json"], []),
            "created_at": row["created_at"],
            "last_used_at": row["last_used_at"],
            "use_count": row["use_count"],
            "notes": row["notes"],
        }
        for row in rows
    ]


def delete_source_group(group_id: str) -> bool:
    """Delete a source group. Returns True if a row was deleted."""
    ensure_store_ready()
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM source_groups WHERE group_id = ?", (group_id,))
        conn.commit()
        return cursor.rowcount > 0
