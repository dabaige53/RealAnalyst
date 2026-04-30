#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                records.append(json.loads(text))
    return records


def _flatten_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, (int, float, bool)):
        yield str(value)
        return
    if isinstance(value, list):
        for item in value:
            yield from _flatten_values(item)


def _normalize_text(value: str) -> str:
    return " ".join(value.replace("_", " ").casefold().split())


def record_text(record: dict[str, Any]) -> str:
    return _normalize_text(" ".join(text for value in record.values() for text in _flatten_values(value)))


def _query_terms(query: str) -> list[str]:
    return [term for term in _normalize_text(query).split() if term]


def score_record(record: dict[str, Any], query: str) -> int:
    normalized_query = _normalize_text(query)
    terms = _query_terms(query)
    if not terms:
        return 0

    text = record_text(record)
    score = 0
    if normalized_query and normalized_query in text:
        score += len(terms) + 1
    score += sum(1 for term in terms if term in text)
    return score


def search_records(records: Iterable[dict[str, Any]], query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    if not _query_terms(query) or limit <= 0:
        return []

    scored = [
        (score, index, record)
        for index, record in enumerate(records)
        if (score := score_record(record, query)) > 0
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [record for _, _, record in scored[:limit]]


def _fts5_match_expr(query: str, record_type: str | None = None) -> tuple[str, list[str]]:
    """Build an FTS5 MATCH expression from a query string.

    Keep CJK words intact because SQLite unicode61 indexes contiguous Chinese
    text as whole tokens. Prefix matching keeps partial inputs such as "客座"
    useful for "客座率".
    The ``record_type`` filter (if given) is prepended as an AND clause.
    """
    terms: list[str] = []
    for term in _query_terms(query):
        if term not in terms:
            terms.append(term)
    if not terms:
        return "", []
    body = " OR ".join(f'"{t.replace(chr(34), chr(34) + chr(34))}"*' for t in terms)
    if record_type and record_type not in ("all",):
        expr = f'record_type:"{record_type}" AND ({body})'
    else:
        expr = body
    return expr, terms


def search_fts5(
    db_path: Path,
    query: str,
    *,
    record_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search the FTS5 index at *db_path* and return matching records sorted by BM25."""
    import sqlite3

    if not db_path.exists():
        return []

    expr, terms = _fts5_match_expr(query, record_type)
    if not expr:
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT payload, bm25(search_index) AS rank FROM search_index WHERE search_index MATCH ? ORDER BY rank LIMIT ?",
            (expr, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

    results: list[dict[str, Any]] = []
    for row in rows:
        try:
            results.append(json.loads(row["payload"]))
        except (json.JSONDecodeError, KeyError):
            continue
    return results
