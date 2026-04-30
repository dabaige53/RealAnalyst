from __future__ import annotations

import re
from typing import Any


KNOWN_VALUE_PATTERNS: tuple[dict[str, str], ...] = (
    {
        "kind": "datetime",
        "label": "YYYY-MM-DD HH:MM:SS",
        "regex": r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",
        "example": "2026-04-15 00:00:00",
    },
    {
        "kind": "iso_datetime",
        "label": "YYYY-MM-DDTHH:MM:SS",
        "regex": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$",
        "example": "2026-04-15T00:00:00",
    },
    {
        "kind": "date",
        "label": "YYYY-MM-DD",
        "regex": r"^\d{4}-\d{2}-\d{2}$",
        "example": "2026-04-15",
    },
    {
        "kind": "date_range",
        "label": "YYYY-MM-DD|YYYY-MM-DD",
        "regex": r"^\d{4}-\d{2}-\d{2}\|\d{4}-\d{2}-\d{2}$",
        "example": "2026-04-01|2026-04-30",
    },
    {
        "kind": "month",
        "label": "YYYY-MM",
        "regex": r"^\d{4}-\d{2}$",
        "example": "2026-04",
    },
)


def clean_sample_values(values: list[Any]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text in cleaned:
            continue
        cleaned.append(text)
    return cleaned


def infer_value_pattern(values: list[Any]) -> dict[str, Any] | None:
    cleaned = clean_sample_values(values)
    if not cleaned:
        return None
    for pattern in KNOWN_VALUE_PATTERNS:
        regex = pattern["regex"]
        if all(re.fullmatch(regex, value) for value in cleaned):
            return {
                "kind": pattern["kind"],
                "label": pattern["label"],
                "regex": regex,
                "example": cleaned[0],
                "sample_count": len(cleaned),
            }
    return None


def compact_sample_values(values: list[Any], *, limit: int) -> list[str]:
    pattern = infer_value_pattern(values)
    if pattern:
        return [str(pattern["example"])]
    return clean_sample_values(values)[:limit]


def validation_from_samples(values: list[Any]) -> dict[str, Any]:
    pattern = infer_value_pattern(values)
    if not pattern:
        return {}
    return {
        "mode": "strict",
        "pattern": pattern["regex"],
        "example": pattern["example"],
        "label": pattern["label"],
    }


def declared_field_pattern(*, role: str, data_type: str, field_name: str = "") -> dict[str, str] | None:
    role_l = role.strip().lower()
    type_l = data_type.strip().lower()
    name_l = field_name.strip().lower()

    if type_l in {"timestamp", "datetime"}:
        return dict(KNOWN_VALUE_PATTERNS[0])
    if type_l == "date":
        return dict(KNOWN_VALUE_PATTERNS[2])
    if type_l in {"month", "year_month"}:
        return dict(KNOWN_VALUE_PATTERNS[4])
    if role_l == "time_dimension" and "month" in name_l:
        return dict(KNOWN_VALUE_PATTERNS[4])
    return None
