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
