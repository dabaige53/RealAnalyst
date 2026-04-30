#!/usr/bin/env python3
"""Build lightweight dataset catalog summaries for multi-dataset discovery."""
from __future__ import annotations

from typing import Any


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _truncate(text: str, max_length: int = 80) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def _has_review_flag(items: list[Any]) -> bool:
    for item in items:
        if not isinstance(item, dict):
            continue
        definition = item.get("business_definition")
        if isinstance(definition, dict) and definition.get("needs_review") is True:
            return True
    return False


def dataset_summary(dataset: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal summary for one normalized dataset."""
    business = dataset.get("business") if isinstance(dataset.get("business"), dict) else {}
    fields = [f for f in _as_list(dataset.get("fields")) if isinstance(f, dict)]
    metrics = [m for m in _as_list(dataset.get("metrics")) if isinstance(m, dict)]
    metric_names = [_as_text(m.get("name")) for m in metrics if _as_text(m.get("name"))]

    return {
        "id": _as_text(dataset.get("id")),
        "display_name": _as_text(dataset.get("display_name")),
        "domain": _as_text(business.get("domain")),
        "description": _truncate(_as_text(dataset.get("description") or business.get("description"))),
        "grain": _as_list(business.get("grain")),
        "time_fields": _as_list(business.get("time_fields")),
        "top_metrics": metric_names[:3],
        "suitable_for": _as_list(business.get("suitable_for")),
        "field_count": len(fields),
        "metric_count": len(metrics),
        "review_required": _has_review_flag(fields) or _has_review_flag(metrics),
    }


def build_catalog(
    datasets: list[dict[str, Any]],
    *,
    domain: str | None = None,
    group_by_domain: bool = False,
) -> dict[str, Any]:
    """Build a catalog of dataset summaries with optional filtering and grouping."""
    summaries = [dataset_summary(ds) for ds in datasets]

    if domain:
        domain_lower = domain.lower()
        summaries = [s for s in summaries if s["domain"].lower() == domain_lower]

    domain_counts: dict[str, int] = {}
    for s in summaries:
        d = s["domain"] or "(none)"
        domain_counts[d] = domain_counts.get(d, 0) + 1

    result: dict[str, Any] = {
        "total": len(summaries),
        "domain_summary": domain_counts,
    }

    if group_by_domain:
        groups: dict[str, list[dict[str, Any]]] = {}
        for s in summaries:
            d = s["domain"] or "(none)"
            groups.setdefault(d, []).append(s)
        result["groups"] = groups
    else:
        result["datasets"] = summaries

    return result
