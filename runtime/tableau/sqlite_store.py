#!/usr/bin/env python3
"""SQLite-backed unified registry/spec store.

Current runtime truth is stored in `runtime/registry.db`.
The old `runtime/tableau/registry.db` path is read once as a compatibility
source when the new database does not exist.
No YAML bootstrap or YAML refresh path is retained here.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

_WORKSPACE_DIR = Path(__file__).resolve().parents[2]
_RUNTIME_DIR = _WORKSPACE_DIR / "runtime"
_DB_PATH = _RUNTIME_DIR / "registry.db"
_LEGACY_DB_PATH = Path(__file__).resolve().parent / "registry.db"


def workspace_dir() -> Path:
    return _WORKSPACE_DIR


def runtime_dir() -> Path:
    return _RUNTIME_DIR


def db_path() -> Path:
    return _DB_PATH


def legacy_db_path() -> Path:
    return _LEGACY_DB_PATH


def active_db_path() -> Path:
    return _DB_PATH if _DB_PATH.exists() or not _LEGACY_DB_PATH.exists() else _LEGACY_DB_PATH


def _ensure_primary_db_path() -> None:
    if _DB_PATH.exists() or not _LEGACY_DB_PATH.exists() or _DB_PATH == _LEGACY_DB_PATH:
        return
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_LEGACY_DB_PATH, _DB_PATH)


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
    _ensure_primary_db_path()
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
        """
    )
    conn.commit()


def migrate_from_yaml(*, force: bool = False) -> dict[str, int]:
    """Legacy no-op kept only for old script entrypoints."""
    ensure_store_ready(force_migrate=False)
    return {"db_path": str(_DB_PATH), "note": "YAML migration path removed; runtime is already SQLite-only"}


def migrate_specs_enums_from_yaml(*, force: bool = False) -> dict[str, int]:
    """Legacy no-op kept only for old script entrypoints."""
    ensure_store_ready(force_migrate=False)
    return {"db_path": str(_DB_PATH), "note": "YAML refresh path removed; runtime is already SQLite-only"}


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
