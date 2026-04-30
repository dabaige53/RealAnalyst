#!/usr/bin/env python3
"""Reconcile runtime registry lookup tables vs metadata dictionaries/datasets."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


# ---------------------------------------------------------------------------
# Runtime side: read metrics / dimensions / glossary from runtime/registry.db
# ---------------------------------------------------------------------------

def _load_runtime_metrics(db_path: Path) -> dict[str, str]:
    """Return {metric_id: definition} from runtime lookup tables."""
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT metric_id, definition FROM metrics").fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()
    return {str(r["metric_id"]): _as_text(r["definition"]) for r in rows}


def _load_runtime_dimensions(db_path: Path) -> dict[str, str]:
    """Return {dimension_id: name} from runtime lookup tables."""
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT dimension_id, name FROM dimensions").fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()
    return {str(r["dimension_id"]): _as_text(r["name"]) for r in rows}


def _load_runtime_glossary(db_path: Path) -> dict[str, str]:
    """Return {item_key: name} from runtime lookup tables."""
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT item_key, name FROM glossary_items").fetchall()
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()
    return {str(r["item_key"]): _as_text(r["name"]) for r in rows}


# ---------------------------------------------------------------------------
# Metadata side: extract metrics / dimensions / glossary from YAML datasets + dicts
# ---------------------------------------------------------------------------

def _extract_metadata_metrics(datasets: list[dict[str, Any]], dictionaries: list[dict[str, Any]]) -> dict[str, str]:
    """Return {metric_name: definition_text} from metadata YAML."""
    result: dict[str, str] = {}
    sources = [*datasets, *dictionaries]
    for source in sources:
        for metric in _as_list(source.get("metrics")):
            if not isinstance(metric, dict):
                continue
            name = _as_text(metric.get("name"))
            if not name:
                continue
            definition = metric.get("business_definition")
            def_text = _as_text(definition.get("text") if isinstance(definition, dict) else definition)
            if name not in result:
                result[name] = def_text
    return result


def _extract_metadata_dimensions(datasets: list[dict[str, Any]], dictionaries: list[dict[str, Any]]) -> dict[str, str]:
    """Return {field_name: display_name} for dimension-role fields from metadata."""
    result: dict[str, str] = {}
    sources = [*datasets, *dictionaries]
    for source in sources:
        for field in _as_list(source.get("fields")):
            if not isinstance(field, dict):
                continue
            if _as_text(field.get("role")).lower() not in ("dimension", "dim"):
                continue
            name = _as_text(field.get("name"))
            if name and name not in result:
                result[name] = _as_text(field.get("display_name"))
    return result


def _extract_metadata_glossary(datasets: list[dict[str, Any]], dictionaries: list[dict[str, Any]]) -> dict[str, str]:
    """Return {key: display_name} from metadata glossary sections."""
    result: dict[str, str] = {}
    sources = [*datasets, *dictionaries]
    for source in sources:
        for item in _as_list(source.get("glossary")):
            if not isinstance(item, dict):
                continue
            key = _as_text(item.get("key") or item.get("item_key") or item.get("display_name"))
            if key and key not in result:
                result[key] = _as_text(item.get("display_name"))
    return result


# ---------------------------------------------------------------------------
# Reconcile logic
# ---------------------------------------------------------------------------

def _reconcile_category(
    runtime_items: dict[str, str],
    metadata_items: dict[str, str],
    runtime_def_label: str = "runtime_def",
    metadata_def_label: str = "metadata_def",
) -> dict[str, Any]:
    """Compare two {name: definition} dicts and return reconciliation summary."""
    runtime_keys = set(runtime_items)
    metadata_keys = set(metadata_items)
    matched_keys = runtime_keys & metadata_keys
    only_runtime = sorted(runtime_keys - metadata_keys)
    only_metadata = sorted(metadata_keys - runtime_keys)

    mismatches: list[dict[str, str]] = []
    for key in sorted(matched_keys):
        r_def = runtime_items[key]
        m_def = metadata_items[key]
        if r_def and m_def and r_def != m_def:
            mismatches.append({
                "name": key,
                runtime_def_label: r_def,
                metadata_def_label: m_def,
            })

    return {
        "matched": len(matched_keys),
        "only_in_runtime": only_runtime,
        "only_in_metadata": only_metadata,
        "definition_mismatch": mismatches,
    }


def reconcile(
    runtime_config_db: Path,
    datasets: list[dict[str, Any]],
    dictionaries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run full reconciliation between runtime lookup tables and metadata YAML."""
    return {
        "success": True,
        "runtime_config_db": str(runtime_config_db),
        "metrics": _reconcile_category(
            _load_runtime_metrics(runtime_config_db),
            _extract_metadata_metrics(datasets, dictionaries),
        ),
        "dimensions": _reconcile_category(
            _load_runtime_dimensions(runtime_config_db),
            _extract_metadata_dimensions(datasets, dictionaries),
            runtime_def_label="runtime_name",
            metadata_def_label="metadata_display_name",
        ),
        "glossary": _reconcile_category(
            _load_runtime_glossary(runtime_config_db),
            _extract_metadata_glossary(datasets, dictionaries),
            runtime_def_label="runtime_name",
            metadata_def_label="metadata_display_name",
        ),
    }
