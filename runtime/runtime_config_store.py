#!/usr/bin/env python3
"""SQLite-backed runtime lookup store.

Structured runtime metadata lives in the global runtime database:
`runtime/registry.db`.
"""

from __future__ import annotations

import importlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

_WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
_SITE_PACKAGES = next(
    (( _WORKSPACE_ROOT / ".venv" / "lib").glob("python*/site-packages")),
    None,
)
if _SITE_PACKAGES and str(_SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(_SITE_PACKAGES))

_RUNTIME_DIR = Path(__file__).resolve().parent
try:
    from runtime.paths import runtime_db_path
except ModuleNotFoundError:  # invoked with runtime/ on sys.path
    from paths import runtime_db_path  # type: ignore[no-redef]

_DB_PATH = runtime_db_path()

# NOTE: Only these structured lookup families are mirrored into SQLite.
# - metrics / dimensions / glossary
# Templates/frameworks/workflow/long prose remain YAML/Markdown only.
_YAML_DOCS: dict[str, Path] = {
    "metrics": _RUNTIME_DIR / "metrics.yaml",
    "dimensions": _RUNTIME_DIR / "dimensions.yaml",
    "glossary": _RUNTIME_DIR / "glossary.yaml",
}

_SECTION_TYPE_HINTS = {
    "airlines": "airline",
    "airports": "airport",
    "terms": "term",
}


def _yaml_module() -> Any:
    try:
        return importlib.import_module("yaml")
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("PyYAML is required to bootstrap runtime lookup tables") from exc


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

        CREATE TABLE IF NOT EXISTS documents (
            doc_key TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            updated TEXT,
            payload_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS metrics (
            metric_id TEXT PRIMARY KEY,
            name_cn TEXT,
            aliases_json TEXT NOT NULL DEFAULT '[]',
            unit TEXT,
            definition TEXT,
            category_key TEXT,
            category_name TEXT,
            group_key TEXT,
            benchmark_json TEXT,
            payload_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_metrics_name_cn ON metrics(name_cn);

        CREATE TABLE IF NOT EXISTS metric_aliases (
            metric_id TEXT NOT NULL,
            alias TEXT NOT NULL,
            PRIMARY KEY (metric_id, alias),
            FOREIGN KEY (metric_id) REFERENCES metrics(metric_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_metric_aliases_alias ON metric_aliases(alias);

        CREATE TABLE IF NOT EXISTS metric_benchmarks (
            metric_id TEXT NOT NULL,
            level TEXT NOT NULL,
            expr TEXT NOT NULL,
            PRIMARY KEY (metric_id, level),
            FOREIGN KEY (metric_id) REFERENCES metrics(metric_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_metric_benchmarks_level ON metric_benchmarks(level);

        CREATE TABLE IF NOT EXISTS dimensions (
            dimension_id TEXT PRIMARY KEY,
            name TEXT,
            category_key TEXT,
            category_name TEXT,
            payload_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_dimensions_name ON dimensions(name);
        CREATE INDEX IF NOT EXISTS idx_dimensions_category ON dimensions(category_key);

        CREATE TABLE IF NOT EXISTS dimension_fields (
            dimension_id TEXT NOT NULL,
            field_id TEXT NOT NULL,
            field_name TEXT,
            field_type TEXT,
            definition TEXT,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (dimension_id, field_id),
            FOREIGN KEY (dimension_id) REFERENCES dimensions(dimension_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_dimension_fields_name ON dimension_fields(field_name);

        CREATE TABLE IF NOT EXISTS glossary_items (
            section TEXT NOT NULL,
            item_key TEXT NOT NULL,
            name TEXT,
            name_en TEXT,
            item_type TEXT,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (section, item_key)
        );

        CREATE INDEX IF NOT EXISTS idx_glossary_name ON glossary_items(name);

        """
    )
    conn.commit()


def _load_yaml(path: Path) -> Any:
    yaml = _yaml_module()
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = _load_yaml(path) or {}
    return payload if isinstance(payload, dict) else {}


def _yaml_snapshot() -> dict[str, int]:
    snapshot: dict[str, int] = {}
    for doc_key, path in _YAML_DOCS.items():
        if path.exists():
            snapshot[doc_key] = path.stat().st_mtime_ns
    return snapshot


def _stored_yaml_snapshot(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        "SELECT value_json FROM metadata WHERE key = 'yaml_snapshot' LIMIT 1"
    ).fetchone()
    if not row:
        return {}
    payload = _json_loads(row["value_json"], {})
    if not isinstance(payload, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in payload.items():
        try:
            out[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return out


def _needs_migration(conn: sqlite3.Connection) -> bool:
    current = _yaml_snapshot()
    if not current:
        return False
    stored = _stored_yaml_snapshot(conn)
    return current != stored


def db_path() -> Path:
    return _DB_PATH


def migrate_from_yaml(*, force: bool = False) -> dict[str, int]:
    docs = {doc_key: _load_yaml_dict(path) for doc_key, path in _YAML_DOCS.items()}

    metrics_doc = docs.get("metrics", {})
    dimensions_doc = docs.get("dimensions", {})
    glossary_doc = docs.get("glossary", {})
    metrics_count = 0
    dimensions_count = 0
    dimension_fields_count = 0
    glossary_count = 0

    with _connect() as conn:
        if force:
            conn.execute("DELETE FROM metadata WHERE key = 'yaml_snapshot'")
            conn.execute("DELETE FROM documents")
            conn.execute("DELETE FROM metric_benchmarks")
            conn.execute("DELETE FROM metric_aliases")
            conn.execute("DELETE FROM dimension_fields")
            conn.execute("DELETE FROM metrics")
            conn.execute("DELETE FROM dimensions")
            conn.execute("DELETE FROM glossary_items")

        for doc_key, payload in docs.items():
            conn.execute(
                """
                INSERT OR REPLACE INTO documents(doc_key, source_path, updated, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    doc_key,
                    str(_YAML_DOCS[doc_key].relative_to(_WORKSPACE_ROOT)),
                    payload.get("updated"),
                    _json_dumps(payload),
                ),
            )

        categories = metrics_doc.get("categories", {})
        if isinstance(categories, dict):
            for category_key, category_data in categories.items():
                if not isinstance(category_data, dict):
                    continue
                category_name = category_data.get("name", category_key)
                for group_key, group_data in category_data.items():
                    if group_key in ("name", "description") or not isinstance(group_data, list):
                        continue
                    for metric in group_data:
                        if not isinstance(metric, dict):
                            continue
                        metric_id = metric.get("id")
                        if not isinstance(metric_id, str) or not metric_id:
                            continue
                        aliases = metric.get("aliases") or []
                        benchmark = metric.get("benchmark") or {}
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO metrics(
                                metric_id, name_cn, aliases_json, unit, definition,
                                category_key, category_name, group_key, benchmark_json, payload_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                metric_id,
                                metric.get("name_cn"),
                                _json_dumps(aliases),
                                metric.get("unit"),
                                metric.get("definition"),
                                category_key,
                                category_name,
                                group_key,
                                _json_dumps(benchmark) if benchmark else None,
                                _json_dumps(metric),
                            ),
                        )

                        if isinstance(aliases, list):
                            for alias in aliases:
                                if not isinstance(alias, str) or not alias.strip():
                                    continue
                                conn.execute(
                                    "INSERT OR REPLACE INTO metric_aliases(metric_id, alias) VALUES (?, ?)",
                                    (metric_id, alias.strip()),
                                )

                        if isinstance(benchmark, dict):
                            for level, expr in benchmark.items():
                                if not isinstance(level, str) or not isinstance(expr, str):
                                    continue
                                if not level.strip() or not expr.strip():
                                    continue
                                conn.execute(
                                    "INSERT OR REPLACE INTO metric_benchmarks(metric_id, level, expr) VALUES (?, ?, ?)",
                                    (metric_id, level.strip(), expr.strip()),
                                )

                        metrics_count += 1

        dimensions = dimensions_doc.get("dimensions", {})
        if isinstance(dimensions, dict):
            for category_key, category_data in dimensions.items():
                if not isinstance(category_data, dict):
                    continue
                category_name = category_data.get("name", category_key)
                for dimension_id, dimension_data in category_data.items():
                    if dimension_id in ("name", "description") or not isinstance(dimension_data, dict):
                        continue
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO dimensions(
                            dimension_id, name, category_key, category_name, payload_json
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            dimension_id,
                            dimension_data.get("name", dimension_id),
                            category_key,
                            category_name,
                            _json_dumps(dimension_data),
                        ),
                    )
                    dimensions_count += 1

                    fields = dimension_data.get("fields")
                    if isinstance(fields, list):
                        for field in fields:
                            if not isinstance(field, dict):
                                continue
                            field_id = field.get("id")
                            if not isinstance(field_id, str) or not field_id:
                                continue
                            conn.execute(
                                """
                                INSERT OR REPLACE INTO dimension_fields(
                                    dimension_id, field_id, field_name, field_type, definition, payload_json
                                ) VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    dimension_id,
                                    field_id,
                                    field.get("name"),
                                    field.get("type"),
                                    field.get("definition"),
                                    _json_dumps(field),
                                ),
                            )
                            dimension_fields_count += 1

        for section, section_payload in glossary_doc.items():
            if section in {"version", "updated"} or not isinstance(section_payload, dict):
                continue
            for item_key, item_payload in section_payload.items():
                if not isinstance(item_payload, dict):
                    continue
                item_name = (
                    item_payload.get("name")
                    or item_payload.get("name_cn")
                    or item_payload.get("full_name")
                )
                item_name_en = item_payload.get("name_en")
                item_type = item_payload.get("type") or _SECTION_TYPE_HINTS.get(section)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO glossary_items(
                        section, item_key, name, name_en, item_type, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        section,
                        str(item_key),
                        item_name,
                        item_name_en,
                        item_type,
                        _json_dumps(item_payload),
                    ),
                )
                glossary_count += 1

        conn.execute(
            "INSERT OR REPLACE INTO metadata(key, value_json) VALUES (?, ?)",
            ("yaml_snapshot", _json_dumps(_yaml_snapshot())),
        )
        conn.commit()

    return {
        "documents": len(docs),
        "metrics": metrics_count,
        "dimensions": dimensions_count,
        "dimension_fields": dimension_fields_count,
        "glossary_items": glossary_count,
    }


def ensure_store_ready(*, force_migrate: bool = False) -> Path:
    if force_migrate or not _DB_PATH.exists():
        migrate_from_yaml(force=True)
        return _DB_PATH

    with _connect() as conn:
        if _needs_migration(conn):
            migrate_from_yaml(force=True)
    return _DB_PATH


def load_document(doc_key: str) -> dict[str, Any] | None:
    ensure_store_ready()
    with _connect() as conn:
        row = conn.execute(
            "SELECT payload_json FROM documents WHERE doc_key = ? LIMIT 1", (doc_key,)
        ).fetchone()
    if not row:
        return None
    payload = _json_loads(row["payload_json"], {})
    return payload if isinstance(payload, dict) else None


def search_metrics(keyword: str) -> list[dict[str, Any]]:
    ensure_store_ready()
    pattern = f"%{keyword.lower()}%"

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT m.metric_id, m.name_cn, m.unit, m.definition, m.category_name, m.aliases_json
            FROM metrics m
            LEFT JOIN metric_aliases a ON a.metric_id = m.metric_id
            WHERE lower(m.metric_id) LIKE ?
               OR lower(coalesce(m.name_cn, '')) LIKE ?
               OR lower(coalesce(a.alias, '')) LIKE ?
            ORDER BY m.category_key, m.group_key, m.metric_id
            """,
            (pattern, pattern, pattern),
        ).fetchall()

        metric_ids = [str(r["metric_id"]) for r in rows]
        bench_map: dict[str, dict[str, str]] = {}
        if metric_ids:
            placeholders = ",".join(["?"] * len(metric_ids))
            bench_rows = conn.execute(
                f"SELECT metric_id, level, expr FROM metric_benchmarks WHERE metric_id IN ({placeholders})",
                metric_ids,
            ).fetchall()
            for br in bench_rows:
                mid = str(br["metric_id"])
                bench_map.setdefault(mid, {})[str(br["level"])] = str(br["expr"])

    out: list[dict[str, Any]] = []
    for row in rows:
        metric_id = str(row["metric_id"])
        out.append(
            {
                "id": metric_id,
                "name_cn": row["name_cn"],
                "unit": row["unit"],
                "definition": row["definition"],
                "category": row["category_name"] or "",
                "aliases": _json_loads(row["aliases_json"], []),
                "benchmark": bench_map.get(metric_id, {}),
            }
        )
    return out


def _load_dimension_fields(conn: sqlite3.Connection, dimension_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT field_id, field_name, field_type
        FROM dimension_fields
        WHERE dimension_id = ?
        ORDER BY field_id
        """,
        (dimension_id,),
    ).fetchall()
    return [
        {"id": row["field_id"], "name": row["field_name"], "type": row["field_type"]}
        for row in rows
    ]


def search_dimensions(keyword: str) -> list[dict[str, Any]]:
    ensure_store_ready()
    pattern = f"%{keyword.lower()}%"
    out: list[dict[str, Any]] = []
    direct_ids: set[str] = set()

    with _connect() as conn:
        dim_rows = conn.execute(
            """
            SELECT dimension_id, name, category_name
            FROM dimensions
            WHERE lower(dimension_id) LIKE ?
               OR lower(coalesce(name, '')) LIKE ?
            ORDER BY category_key, dimension_id
            """,
            (pattern, pattern),
        ).fetchall()

        for row in dim_rows:
            dimension_id = str(row["dimension_id"])
            direct_ids.add(dimension_id)
            out.append(
                {
                    "id": dimension_id,
                    "name": row["name"] or dimension_id,
                    "category": row["category_name"] or "",
                    "fields": _load_dimension_fields(conn, dimension_id)[:5],
                }
            )

        field_rows = conn.execute(
            """
            SELECT d.dimension_id, d.name AS dimension_name, d.category_name,
                   f.field_id, f.field_name, f.field_type, f.definition
            FROM dimension_fields f
            JOIN dimensions d ON d.dimension_id = f.dimension_id
            WHERE lower(f.field_id) LIKE ?
               OR lower(coalesce(f.field_name, '')) LIKE ?
            ORDER BY d.category_key, d.dimension_id, f.field_id
            """,
            (pattern, pattern),
        ).fetchall()

    for row in field_rows:
        dimension_id = str(row["dimension_id"])
        if dimension_id in direct_ids:
            continue
        out.append(
            {
                "id": dimension_id,
                "name": row["dimension_name"] or dimension_id,
                "category": row["category_name"] or "",
                "matched_field": {
                    "id": row["field_id"],
                    "name": row["field_name"],
                    "type": row["field_type"],
                    "definition": row["definition"] or "",
                },
            }
        )
        direct_ids.add(dimension_id)

    return out


def search_glossary(keyword: str) -> list[dict[str, Any]]:
    ensure_store_ready()
    pattern = f"%{keyword.lower()}%"
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT section, item_key, name, name_en, item_type
            FROM glossary_items
            WHERE lower(item_key) LIKE ?
               OR lower(coalesce(name, '')) LIKE ?
               OR lower(coalesce(name_en, '')) LIKE ?
            ORDER BY section, item_key
            """,
            (pattern, pattern, pattern),
        ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        section = str(row["section"])
        item_type = _SECTION_TYPE_HINTS.get(section) or row["item_type"] or section
        if section in {"airlines", "airports"}:
            item = {
                "code": row["item_key"],
                "name": row["name"],
                "type": item_type,
            }
            if row["name_en"]:
                item["name_en"] = row["name_en"]
        else:
            item = {
                "key": row["item_key"],
                "name": row["name"],
                "type": item_type,
                "section": section,
            }
            if row["name_en"]:
                item["name_en"] = row["name_en"]
        out.append(item)
    return out
