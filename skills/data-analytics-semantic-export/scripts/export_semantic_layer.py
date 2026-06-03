#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ExportError(ValueError):
    """Raised when semantic-layer export input cannot satisfy the contract."""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = _as_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def _validate_skill_name(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value):
        raise ExportError("--skill-name must use lowercase letters, numbers, and hyphens")
    return value


def _find_workspace(start: Path) -> Path:
    env_root = os.environ.get("ANALYST_WORKSPACE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()
    for candidate in (start, *start.parents):
        if (candidate / "skills").is_dir() and (candidate / "metadata").is_dir():
            return candidate.resolve()
        if (candidate / ".agents" / "skills").is_dir() and (candidate / "metadata").exists():
            return candidate.resolve()
    raise ExportError(f"Cannot find RealAnalyst workspace from {start}")


def _ensure_workspace_on_path(workspace: Path) -> None:
    source_root = Path(__file__).resolve().parents[3]
    roots = [workspace, source_root]
    agents_dir = workspace / ".agents"
    if (agents_dir / "skills").is_dir():
        roots.append(agents_dir)
    metadata_script_dirs = [
        workspace / "skills" / "metadata" / "scripts",
        workspace / ".agents" / "skills" / "metadata" / "scripts",
        source_root / "skills" / "metadata" / "scripts",
    ]
    roots.extend(path for path in metadata_script_dirs if path.is_dir())
    for root in reversed(roots):
        root_text = str(root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
    os.environ["ANALYST_WORKSPACE_DIR"] = str(workspace)


def _rel(workspace: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(workspace.resolve()))
    except ValueError:
        return str(path)


def _truncate(value: Any, limit: int = 220) -> str:
    text = "、".join(_as_text(v) for v in value if _as_text(v)) if isinstance(value, list) else _as_text(value)
    text = re.sub(r"\s+", " ", text).strip()
    text = _redact_sensitive_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _redact_sensitive_text(text: str) -> str:
    text = re.sub(
        r"(?i)(\b(?:password|passwd|pwd|token|access_token|secret|api[_-]?key|dsn)\b\s*[:=]\s*)[^,;\s|`]+",
        r"\1[redacted]",
        text,
    )
    text = re.sub(r"(?i)(://)[^/\s:@|`]+:[^@\s/|`]+@", r"\1[redacted]@", text)
    text = re.sub(
        r"(?i)([?&](?:password|passwd|pwd|token|access_token|secret|api[_-]?key|dsn)=)[^&\s|`]+",
        r"\1[redacted]",
        text,
    )
    return text


def _safe_source_object(value: Any) -> str:
    text = _as_text(value)
    if not text:
        return ""
    if "://" in text or re.search(r"(?i)\b(password|passwd|pwd|token|access_token|secret|api[_-]?key|dsn)\b", text):
        return "[redacted-sensitive-locator]"
    return _redact_sensitive_text(text)


def _md(value: Any, *, empty: str = "未维护", limit: int = 220) -> str:
    text = _truncate(value, limit=limit)
    if not text:
        return empty
    return text.replace("|", r"\|")


def _definition_meta(item: dict[str, Any]) -> dict[str, str]:
    semantic_ref = item.get("semantic_ref") if isinstance(item.get("semantic_ref"), dict) else {}
    status = _as_text(semantic_ref.get("status") or item.get("source_type") or "local_only")
    label = _as_text(semantic_ref.get("label"))
    ref = _as_text(item.get("ref") or semantic_ref.get("ref"))
    caveats: list[str] = []
    if item.get("needs_review"):
        caveats.append("needs_review=true")
    if status == "pending":
        caveats.append("definition pending")
    if not _as_text(item.get("definition")) and not ref:
        caveats.append("definition missing")
    return {
        "status": status,
        "label": label or status,
        "ref": ref,
        "caveat": "；".join(caveats),
    }


def _field_concept(field: dict[str, Any]) -> str:
    role = _as_text(field.get("role")).lower()
    if role == "time_dimension":
        return "Time field / filter"
    if role in {"dimension", "category"}:
        return "Dimension / filter"
    if role == "identifier":
        return "Entity id / join key"
    if role in {"metric_source", "measure", "measure_candidate"}:
        return "Measure source field"
    return "Field"


def _unique_fields(fields: list[Any]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        key = (
            _as_text(field.get("canonical_name") or field.get("name")),
            _as_text(field.get("physical_name")),
            _as_text(field.get("role")),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(field)
    return out


def _unique_metrics(metrics: list[Any]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        key = (
            _as_text(metric.get("canonical_name") or metric.get("name") or metric.get("display_name")),
            _as_text(metric.get("expression")),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(metric)
    return out


def _question_text(value: Any) -> str:
    if isinstance(value, dict):
        question = _as_text(value.get("question") or value.get("text") or value.get("summary"))
        details = []
        for key in ("field", "metric", "reason", "source"):
            if _as_text(value.get(key)):
                details.append(f"{key}: {_as_text(value.get(key))}")
        if question and details:
            return f"{question} ({'; '.join(details)})"
        if question:
            return question
        return "; ".join(f"{key}: {_as_text(item)}" for key, item in value.items() if _as_text(item))
    return _as_text(value)


def _source_locator(dataset: dict[str, Any]) -> str:
    backend = _safe_source_object(dataset.get("source_connector")) or "unknown"
    obj = _safe_source_object(dataset.get("source_object"))
    return f"{backend}:{obj}" if obj else backend


def _load_registry_state(workspace: Path, source_id: str) -> dict[str, Any]:
    registry_path = workspace / "runtime" / "registry.db"
    if not registry_path.exists():
        return {
            "registered": False,
            "status": "not_registered",
            "registry_path": _rel(workspace, registry_path),
            "entry": None,
            "spec": None,
        }

    from runtime.tableau.sqlite_store import get_entry_by_source_id, load_spec_for_entry, load_spec_by_entry_key

    entry = get_entry_by_source_id(source_id)
    spec = load_spec_for_entry(entry) if entry else load_spec_by_entry_key(source_id)
    status = _as_text((entry or {}).get("status"))
    if not status:
        status = "spec_only" if spec else "not_registered"
    return {
        "registered": bool(entry),
        "status": status,
        "registry_path": _rel(workspace, registry_path),
        "entry": entry,
        "spec": spec,
    }


def _load_inputs(workspace: Path, dataset_ids: list[str]) -> list[dict[str, Any]]:
    _ensure_workspace_on_path(workspace)

    from skills.metadata.lib.metadata_context import build_context_pack
    from skills.metadata.lib.metadata_io import (
        iter_dictionary_files,
        iter_mapping_files,
        load_dataset_file,
        load_mapping_file,
        normalize_dataset,
        resolve_dataset_path,
    )
    from skills.metadata.scripts.validate_metadata import validate_dataset

    dictionaries = [load_mapping_file(path) for path in iter_dictionary_files(workspace)]
    mappings = [load_mapping_file(path) for path in iter_mapping_files(workspace)]
    dictionary_paths = {
        _as_text(item.get("id") or item.get("dictionary_id")): path
        for path in iter_dictionary_files(workspace)
        if isinstance((item := load_mapping_file(path)), dict)
    }
    mapping_paths = {
        _as_text(item.get("id") or item.get("mapping_id")): path
        for path in iter_mapping_files(workspace)
        if isinstance((item := load_mapping_file(path)), dict)
    }

    exports: list[dict[str, Any]] = []
    for dataset_id in dataset_ids:
        dataset_path = resolve_dataset_path(workspace, dataset_id)
        raw = load_dataset_file(dataset_path)
        errors = validate_dataset(raw, path=dataset_path)
        if errors:
            raise ExportError(f"{dataset_id} metadata validation failed: {'; '.join(errors[:8])}")
        dataset = normalize_dataset(raw, path=dataset_path)
        pack = build_context_pack(dataset, dictionaries=dictionaries, mappings=mappings)
        runtime = _load_registry_state(workspace, _as_text(pack.get("dataset", {}).get("runtime_source_id") or dataset_id))
        provenance_paths = [_rel(workspace, dataset_path)]
        provenance_paths.extend(
            _rel(workspace, dictionary_paths[ref])
            for ref in pack.get("dictionary_refs", [])
            if ref in dictionary_paths
        )
        provenance_paths.extend(
            _rel(workspace, mapping_paths[ref])
            for ref in pack.get("mapping_refs", [])
            if ref in mapping_paths
        )
        relation_path = workspace / "metadata" / "audit" / "metadata_relations.jsonl"
        if relation_path.exists():
            provenance_paths.append(_rel(workspace, relation_path))
        if runtime.get("registry_path"):
            provenance_paths.append(runtime["registry_path"])

        exports.append(
            {
                "dataset_id": dataset_id,
                "dataset_path": _rel(workspace, dataset_path),
                "pack": pack,
                "runtime": runtime,
                "provenance_paths": _dedupe(provenance_paths),
            }
        )
    return exports


def _coverage_level(exports: list[dict[str, Any]]) -> str:
    if any(item["pack"].get("review_required") for item in exports):
        return "Limited"
    if all(item["runtime"].get("registered") for item in exports):
        return "Directional"
    return "Limited"


def _render_package_skill(*, skill_name: str, area: str) -> str:
    return f"""---
name: {skill_name}
description: Use when answering Data Analytics questions for {area}, including metric definitions, table choice, field mappings, filters, freshness, caveats, and RealAnalyst provenance.
---

# {area} Semantic Layer

Use this skill to answer {area} data questions with the source-backed RealAnalyst context in `references/semantic-layer.md`.

## Start Here

1. Read `references/semantic-layer.md`.
2. Use the listed canonical metrics, fields, source objects, grains, filters, and caveats.
3. Check freshness before answering time-sensitive questions.
4. Treat RealAnalyst metadata as the semantic source of truth, and verify current data through Data Analytics live source reads.

## References

- `references/semantic-layer.md`: metrics, fields, filters, source objects, query patterns, caveats, freshness, and open questions.
- `references/source-inventory.md`: sources checked, coverage level, permissions, gaps, and update boundaries.

## Answering Rules

- Treat this skill as source-selection guidance, not as a substitute for live reads.
- Preserve metric grain, time fields, filters, physical fields, and definition status.
- If this package conflicts with current RealAnalyst metadata, use RealAnalyst metadata as canonical.
- Label stale, inferred, partial, missing-registry, or review-required evidence.
"""


def _render_field_mapping(exports: list[dict[str, Any]]) -> str:
    rows = [
        "| Data Analytics Concept | Display Name | RealAnalyst Field | Physical Field | Role | Type | Source | Definition Ref | Definition Status | Caveat |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in exports:
        dataset = item["pack"]["dataset"]
        source = _source_locator(dataset)
        for field in _unique_fields(item["pack"].get("fields", [])):
            meta = _definition_meta(field)
            rows.append(
                "| "
                + " | ".join(
                    [
                        _md(_field_concept(field)),
                        _md(field.get("display_name")),
                        _md(field.get("canonical_name") or field.get("name")),
                        _md(field.get("physical_name")),
                        _md(field.get("role")),
                        _md(field.get("type")),
                        _md(source),
                        _md(meta["ref"]),
                        _md(meta["label"]),
                        _md(meta["caveat"], empty=""),
                    ]
                )
                + " |"
            )
    if len(rows) == 2:
        rows.append("| 未维护 | 未维护 | 未维护 | 未维护 | 未维护 | 未维护 | 未维护 | 未维护 | 未维护 | 未维护 |")
    return "\n".join(rows)


def _render_metrics(exports: list[dict[str, Any]]) -> str:
    rows = [
        "| Metric | Definition | Expression | Aggregation | Unit | Time Grain | Canonical Source | Caveats |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in exports:
        pack = item["pack"]
        dataset = pack["dataset"]
        source = _source_locator(dataset)
        time_grain = ", ".join(_as_text(v) for v in pack.get("time_fields", []) if _as_text(v)) or "未维护"
        for metric in _unique_metrics(pack.get("metrics", [])):
            meta = _definition_meta(metric)
            caveat = meta["caveat"] or ("dictionary projection" if metric.get("source_layer") == "dictionary" else "")
            rows.append(
                "| "
                + " | ".join(
                    [
                        _md(metric.get("display_name") or metric.get("canonical_name")),
                        _md(metric.get("definition")),
                        _md(metric.get("expression")),
                        _md(metric.get("aggregation")),
                        _md(metric.get("unit")),
                        _md(time_grain),
                        _md(f"{source}; ref={meta['ref']}" if meta["ref"] else source),
                        _md(caveat, empty=""),
                    ]
                )
                + " |"
            )
    if len(rows) == 2:
        return "\n".join(rows) + "\n\n- 当前导出范围没有正式指标；Data Analytics 后续分析不能把字段自动当作 metric。"
    return "\n".join(rows)


def _render_filters(exports: list[dict[str, Any]]) -> str:
    rows = [
        "| Filter Or Dimension | Default Logic | Override When | Applies To | Sources |",
        "| --- | --- | --- | --- | --- |",
    ]
    filter_roles = {"dimension", "time_dimension", "identifier", "category"}
    for item in exports:
        dataset = item["pack"]["dataset"]
        for field in _unique_fields(item["pack"].get("fields", [])):
            role = _as_text(field.get("role")).lower()
            if role not in filter_roles:
                continue
            default_logic = f"Use physical field `{_as_text(field.get('physical_name')) or _as_text(field.get('canonical_name'))}`"
            if role == "time_dimension":
                default_logic += "; preserve date/time boundary"
            rows.append(
                "| "
                + " | ".join(
                    [
                        _md(field.get("display_name") or field.get("canonical_name")),
                        _md(default_logic),
                        _md("Only when live source or user-approved metadata says a different field is canonical"),
                        _md(dataset.get("id")),
                        _md("; ".join(item["provenance_paths"])),
                    ]
                )
                + " |"
            )
    if len(rows) == 2:
        rows.append("| 未维护 | 未维护 | 未维护 | 未维护 | 未维护 |")
    return "\n".join(rows)


def _render_tables(exports: list[dict[str, Any]]) -> str:
    rows = [
        "| Table | When To Use | Grain | Join Keys | Freshness | Caveats | Sources |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in exports:
        pack = item["pack"]
        dataset = pack["dataset"]
        runtime = item["runtime"]
        grain = ", ".join(_as_text(v) for v in pack.get("grain", []) if _as_text(v)) or "未维护"
        time_fields = ", ".join(_as_text(v) for v in pack.get("time_fields", []) if _as_text(v)) or "未维护"
        source = _source_locator(dataset)
        caveats = []
        if not runtime.get("registered"):
            caveats.append("runtime registry not registered")
        if pack.get("review_required"):
            caveats.append("metadata review required")
        rows.append(
            "| "
            + " | ".join(
                [
                    _md(source),
                    _md("; ".join(pack.get("suitable_for", [])) or "Use for questions covered by this dataset metadata"),
                    _md(grain),
                    _md(grain),
                    _md(f"Check live source freshness; time fields: {time_fields}"),
                    _md("；".join(caveats), empty=""),
                    _md("; ".join(item["provenance_paths"])),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _render_open_questions(exports: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in exports:
        dataset_id = item["dataset_id"]
        pack = item["pack"]
        for question in pack.get("pending_questions", []):
            lines.extend(
                [
                    f"- Question: {_md(_question_text(question))}",
                    f"  - Why it matters: affects Data Analytics answers for `{dataset_id}`.",
                    "  - Best owner or source to check next: RealAnalyst metadata maintenance flow.",
                ]
            )
        if not item["runtime"].get("registered"):
            lines.extend(
                [
                    f"- Question: `{dataset_id}` runtime registry is not registered.",
                    "  - Why it matters: Data Analytics can use semantics, but live source access still needs verification.",
                    "  - Best owner or source to check next: `RA:metadata sync-registry` or the relevant source connector setup.",
                ]
            )
        if pack.get("missing_fields") or pack.get("missing_metrics"):
            missing = ", ".join(_as_text(v) for v in [*pack.get("missing_fields", []), *pack.get("missing_metrics", [])] if _as_text(v))
            lines.extend(
                [
                    f"- Question: requested metadata references are missing: {_md(missing)}.",
                    "  - Why it matters: future analysis may choose incomplete fields or metrics.",
                    "  - Best owner or source to check next: RealAnalyst metadata YAML and dictionary refs.",
                ]
            )
    if not lines:
        return "- 无显式未决问题；仍需在 Data Analytics 分析时做 live source verification。"
    return "\n".join(lines)


def _render_semantic_layer(*, area: str, skill_name: str, exports: list[dict[str, Any]], generated_at: str) -> str:
    coverage = _coverage_level(exports)
    dataset_ids = [item["dataset_id"] for item in exports]
    provenance = _dedupe([path for item in exports for path in item["provenance_paths"]])
    freshness = "Semantic projection generated from RealAnalyst metadata; current data freshness must be verified by Data Analytics before time-sensitive answers."
    default_time = _dedupe([_as_text(field) for item in exports for field in item["pack"].get("time_fields", [])])
    caveats = [
        "This semantic-layer package is a usage projection; RealAnalyst metadata remains canonical.",
        "Do not treat this package as proof of current row counts, freshness, or source availability.",
        "Data Analytics user-context is not written automatically; register only after user approval.",
    ]
    for item in exports:
        pack = item["pack"]
        if pack.get("review_required"):
            caveats.append(f"{item['dataset_id']} has needs_review metadata.")
        for note in pack.get("not_suitable_for", []):
            caveats.append(f"{item['dataset_id']}: {_as_text(note)}")

    entity_rows = [
        "| Entity | Means | Does Not Mean | Primary IDs | Grain Notes | Sources |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in exports:
        dataset = item["pack"]["dataset"]
        entity_rows.append(
            "| "
            + " | ".join(
                [
                    _md(dataset.get("display_name") or dataset.get("id")),
                    _md(dataset.get("description") or dataset.get("id")),
                    _md("Live data extract or Data Analytics report output"),
                    _md(dataset.get("runtime_source_id") or dataset.get("id")),
                    _md(", ".join(_as_text(v) for v in item["pack"].get("grain", []) if _as_text(v)) or "未维护"),
                    _md("; ".join(item["provenance_paths"])),
                ]
            )
            + " |"
        )

    docs_rows = [
        "| Source | Use It For | Caveats |",
        "| --- | --- | --- |",
    ]
    for path in provenance:
        docs_rows.append(f"| {_md(path)} | RealAnalyst provenance | {_md('Read-only source for this projection')} |")

    return f"""# {area} Semantic Layer

## Quick Reference

- Area: {area}
- Skill name: `{skill_name}`
- Intended users: Data Analytics agents using RealAnalyst source-backed semantics
- Coverage level: {coverage}
- Source inventory: `references/source-inventory.md`
- Last synthesized: {generated_at}
- Freshness expectations: {freshness}
- Default date and time zone rules: {_md(default_time, empty="No default time field maintained")}
- RealAnalyst canonical source: metadata remains canonical; this package is a semantic projection.
- Dataset ids: {", ".join(f"`{dataset_id}`" for dataset_id in dataset_ids)}
- Provenance paths: {", ".join(f"`{path}`" for path in provenance)}

## Entity Clarification

{chr(10).join(entity_rows)}

## Key Metrics

{_render_metrics(exports)}

## Field Mapping

{_render_field_mapping(exports)}

## Standard Filters And Dimensions

{_render_filters(exports)}

## Key Tables

{_render_tables(exports)}

## Query Patterns

- Pattern: RealAnalyst-guided live source analysis
  - Use when: Data Analytics needs to answer questions covered by the listed dataset ids.
  - Key tables: {", ".join(_source_locator(item["pack"]["dataset"]) for item in exports)}
  - Required filters: preserve maintained time fields, dimensions, physical fields, and definition status.
  - Common joins: only use join keys or grain fields maintained in RealAnalyst metadata.
  - Example skeleton: choose metric from Key Metrics, choose physical fields from Field Mapping, then verify current data through a live Data Analytics source read.

## Gotchas

{chr(10).join(f"- {caveat}" for caveat in _dedupe(caveats))}

## Related Dashboards And Docs

{chr(10).join(docs_rows)}

## Open Questions

{_render_open_questions(exports)}
"""


def _source_inventory_rows(exports: list[dict[str, Any]], generated_at: str) -> str:
    rows = [
        "| Source | Type | Locator | Connector Or Tool | Permission Status | Last Checked | Supports | Gaps Or Caveats | Automation Eligible | Update Boundary |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in exports:
        pack = item["pack"]
        dataset = pack["dataset"]
        runtime = item["runtime"]
        source = _source_locator(dataset)
        permission = "metadata available"
        if runtime.get("registered"):
            permission = f"runtime registry {runtime.get('status')}"
        gaps = []
        if not runtime.get("registered"):
            gaps.append("runtime registry not registered")
        if pack.get("review_required"):
            gaps.append("review required")
        rows.append(
            "| "
            + " | ".join(
                [
                    _md(dataset.get("display_name") or dataset.get("id")),
                    _md(dataset.get("source_connector") or "metadata dataset"),
                    _md(source),
                    _md("RealAnalyst metadata + runtime registry"),
                    _md(permission),
                    _md(generated_at),
                    _md("metrics, fields, dimensions, filters, source choice"),
                    _md("；".join(gaps), empty=""),
                    _md("No; update should be drafted from RealAnalyst metadata refresh"),
                    _md("Read-only projection; do not update RealAnalyst metadata from this package"),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _render_source_inventory(*, exports: list[dict[str, Any]], generated_at: str) -> str:
    coverage = _coverage_level(exports)
    sources_checked = _dedupe([path for item in exports for path in item["provenance_paths"]])
    missing_lanes = []
    if any(not item["runtime"].get("registered") for item in exports):
        missing_lanes.append("runtime/registry.db active registration for at least one dataset")
    missing_lanes.append("Data Analytics live source verification for current data")
    rejected = [
        "Row-level samples were intentionally excluded.",
        "Secrets, DSN, token, and credential material were intentionally excluded.",
        "Data Analytics user-context was not written automatically.",
    ]
    return f"""# Source Inventory

## Coverage

- Coverage level: {coverage}
- Sources checked: {", ".join(f"`{path}`" for path in sources_checked)}
- Missing high-value lanes: {"; ".join(missing_lanes)}
- Rejected or lower-confidence candidates: {"; ".join(rejected)}

## Source Priority

1. RealAnalyst metadata YAML, dictionaries, mappings, and audit paths listed in this inventory are canonical for metric and field meaning.
2. `runtime/registry.db` is used only to check executable source registration and source status.
3. Data Analytics must verify current data, row counts, freshness, and permissions through live source reads before answering time-sensitive questions.

## Sources

{_source_inventory_rows(exports, generated_at)}
"""


def _suggested_user_context_entry(*, area: str, skill_name: str, output_path: Path, generated_at: str) -> str:
    return (
        "# Semantic Layers\n"
        f"- Area: {area}\n"
        f"  Skill Name: {skill_name}\n"
        f"  Skill Path: {output_path}\n"
        f"  Source Inventory Path: {output_path / 'references' / 'source-inventory.md'}\n"
        f"  Last Updated: {generated_at}\n"
        "  Guidance: Use as RealAnalyst semantic projection; verify current data with live Data Analytics source reads.\n"
    )


def _validation_prompt(output_path: Path) -> str:
    return (
        "Load Data Analytics semantic-layer setup.md, skill-template.md, and source-intake.md, then inspect "
        f"the generated package at {output_path}. Check that input datasets, field mappings, metrics, source "
        "inventory, caveats, open questions, and provenance paths are internally consistent, contain no secrets "
        "or row-level samples, and are usable as Data Analytics semantic-layer guidance for later analysis."
    )


def run_export(*, workspace: Path, area: str, dataset_ids: list[str], output_dir: Path | None, skill_name: str | None) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    area_slug = _slug(area, "area")
    resolved_skill_name = _validate_skill_name(skill_name) if skill_name else f"{area_slug}-semantic-layer"
    if output_dir:
        output_path = output_dir.expanduser().resolve()
    else:
        codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")).expanduser().resolve()
        output_path = codex_home / "skills" / resolved_skill_name

    exports = _load_inputs(workspace, dataset_ids)
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    files = {
        output_path / "SKILL.md": _render_package_skill(skill_name=resolved_skill_name, area=area),
        output_path / "references" / "semantic-layer.md": _render_semantic_layer(
            area=area,
            skill_name=resolved_skill_name,
            exports=exports,
            generated_at=generated_at,
        ),
        output_path / "references" / "source-inventory.md": _render_source_inventory(exports=exports, generated_at=generated_at),
    }
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return {
        "success": True,
        "output_path": str(output_path),
        "files_written": [str(path) for path in files],
        "datasets": [
            {
                "dataset_id": item["dataset_id"],
                "dataset_path": item["dataset_path"],
                "field_count": len(_unique_fields(item["pack"].get("fields", []))),
                "metric_count": len(_unique_metrics(item["pack"].get("metrics", []))),
                "runtime_status": item["runtime"].get("status"),
                "review_required": bool(item["pack"].get("review_required")),
            }
            for item in exports
        ],
        "suggested_user_context_entry": _suggested_user_context_entry(
            area=area,
            skill_name=resolved_skill_name,
            output_path=output_path,
            generated_at=generated_at,
        ),
        "data_analytics_validation_prompt": _validation_prompt(output_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export RealAnalyst metadata to a Data Analytics semantic-layer skill package.")
    parser.add_argument("--area", required=True, help="Business/product/reporting area for the generated semantic layer.")
    parser.add_argument("--dataset-id", action="append", required=True, help="RealAnalyst dataset id. Repeat for multiple datasets.")
    parser.add_argument("--output-dir", default=None, help="Package output directory. Defaults to $CODEX_HOME/skills/<skill-name>/")
    parser.add_argument("--skill-name", default=None, help="Generated semantic-layer skill name. Defaults to <area>-semantic-layer.")
    parser.add_argument("--workspace", default=None, help="RealAnalyst workspace. Defaults to ANALYST_WORKSPACE_DIR or auto-discovery.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        workspace = Path(args.workspace).expanduser().resolve() if args.workspace else _find_workspace(Path(__file__).resolve())
        payload = run_export(
            workspace=workspace,
            area=args.area,
            dataset_ids=args.dataset_id,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            skill_name=args.skill_name,
        )
    except Exception as exc:
        error_code = "SEMANTIC_EXPORT_FAILED"
        if isinstance(exc, ExportError):
            error_code = "SEMANTIC_EXPORT_INPUT_INVALID"
        print(
            json.dumps(
                {"success": False, "error": str(exc), "error_code": error_code},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
