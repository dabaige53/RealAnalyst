#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from _common import (
    feedback_path,
    job_dir,
    make_refine_id,
    now_iso,
    read_json,
    read_jsonl,
    relpath,
    resolve_workspace_path,
    runtime_refine_dir,
    workspace_path,
    write_json,
)


def maybe_rel(workspace: Path, path: Path) -> str:
    return relpath(workspace, path) if path.exists() else ""


def column_rows(profile: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    manifest_columns = (((manifest.get("schema") or {}).get("columns")) or []) if isinstance(manifest, dict) else []
    profile_columns = (((profile.get("schema") or {}).get("columns")) or []) if isinstance(profile, dict) else []
    columns = manifest_columns or profile_columns
    result: list[dict[str, Any]] = []
    if isinstance(columns, list):
        for column in columns:
            if not isinstance(column, dict):
                continue
            result.append(
                {
                    "name": column.get("name") or column.get("field") or "",
                    "role": column.get("role") or "",
                    "semantic_type": column.get("semantic_type") or "",
                    "physical_type": column.get("physical_type") or column.get("type") or "",
                }
            )
    return result


def write_feedback_summary(path: Path, records: list[dict[str, Any]]) -> None:
    lines = ["# feedback summary", ""]
    if not records:
        lines.append("No metadata feedback records were found.")
    for idx, record in enumerate(records, start=1):
        lines.extend(
            [
                f"## {idx}. {record.get('summary') or 'metadata review needed'}",
                "",
                f"- issue_type: {record.get('issue_type') or ''}",
                f"- source: {record.get('source') or ''}",
                f"- severity: {record.get('severity') or ''}",
                f"- dataset_id: {record.get('dataset_id') or ''}",
                f"- fields: {', '.join(record.get('fields') or [])}",
                f"- metrics: {', '.join(record.get('metrics') or [])}",
                f"- details: {record.get('details') or ''}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_reference(path: Path, *, dataset_id: str, records: list[dict[str, Any]], columns: list[dict[str, Any]], probe_path: str) -> None:
    lines = [
        "# metadata update reference",
        "",
        f"- dataset_id: {dataset_id}",
        "- purpose: provide evidence and suggestions for RA:metadata; do not treat this file as confirmed YAML.",
        "",
        "## Suggested Review Focus",
        "",
    ]
    if records:
        for record in records:
            lines.append(f"- {record.get('issue_type') or 'metadata_review_needed'}: {record.get('summary') or ''}")
    else:
        lines.append("- Review field definitions, metric formulas, evidence links, and needs_review flags against the profile/probe evidence.")
    lines.extend(["", "## Profile Columns", "", "| field | role | semantic_type | physical_type |", "| --- | --- | --- | --- |"])
    for column in columns:
        lines.append(
            f"| {column.get('name') or ''} | {column.get('role') or ''} | {column.get('semantic_type') or ''} | {column.get('physical_type') or ''} |"
        )
    lines.extend(
        [
            "",
            "## Data Probe",
            "",
            f"- data_probe_summary: {probe_path or 'not generated'}",
            "",
            "## RA:metadata Handoff",
            "",
            "- Update only the relevant dictionaries / mappings / datasets YAML.",
            "- Cite this archived reference pack under `business_definition.source_evidence[].source`.",
            "- Keep uncertain definitions marked with `needs_review: true`.",
            "- Run `metadata validate`, `metadata index`, and `metadata sync-registry --dry-run` after edits.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_brief(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# refine brief",
        "",
        f"- refine_id: {payload['refine_id']}",
        f"- job_id: {payload.get('job_id') or ''}",
        f"- dataset_id: {payload.get('dataset_id') or ''}",
        f"- generated_at: {payload['generated_at']}",
        f"- feedback_count: {payload['feedback_count']}",
        f"- profile_manifest: {payload['inputs'].get('manifest') or ''}",
        f"- profile_json: {payload['inputs'].get('profile') or ''}",
        f"- data_probe: {payload['inputs'].get('data_probe') or ''}",
        "",
        "Next step: archive this pack, then use RA:metadata to update formal YAML.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a metadata refinement reference pack from job evidence.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--refine-id", default="")
    parser.add_argument("--dataset-id", default="")
    parser.add_argument("--probe-dir", default="")
    args = parser.parse_args()

    workspace = workspace_path(args.workspace)
    refine_id = args.refine_id.strip() or make_refine_id(args.session_id)
    out_dir = runtime_refine_dir(workspace, refine_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    job = job_dir(workspace, args.session_id)
    manifest_path = job / "profile" / "manifest.json"
    profile_path = job / "profile" / "profile.json"
    feedback_file = feedback_path(workspace, args.session_id)
    probe_dir = resolve_workspace_path(workspace, args.probe_dir) if args.probe_dir else out_dir
    probe_summary = probe_dir / "data_probe_summary.md" if probe_dir else out_dir / "data_probe_summary.md"
    data_probe = probe_dir / "data_probe.json" if probe_dir else out_dir / "data_probe.json"
    if probe_dir and probe_dir != out_dir:
        for probe_file in (probe_summary, data_probe):
            if probe_file.exists():
                shutil.copy2(probe_file, out_dir / probe_file.name)
        probe_summary = out_dir / "data_probe_summary.md"
        data_probe = out_dir / "data_probe.json"

    manifest = read_json(manifest_path)
    profile = read_json(profile_path)
    records = read_jsonl(feedback_file)
    columns = column_rows(profile, manifest)
    dataset_id = args.dataset_id.strip() or str(manifest.get("id") or profile.get("dataset_id") or "")

    write_feedback_summary(out_dir / "feedback_summary.md", records)
    write_reference(
        out_dir / "metadata_update_reference.md",
        dataset_id=dataset_id,
        records=records,
        columns=columns,
        probe_path=maybe_rel(workspace, probe_summary),
    )

    manifest_payload: dict[str, Any] = {
        "refine_id": refine_id,
        "job_id": args.session_id,
        "dataset_id": dataset_id,
        "generated_at": now_iso(),
        "status": "runtime_draft",
        "inputs": {
            "feedback": maybe_rel(workspace, feedback_file),
            "manifest": maybe_rel(workspace, manifest_path),
            "profile": maybe_rel(workspace, profile_path),
            "data_probe": maybe_rel(workspace, data_probe),
            "data_probe_summary": maybe_rel(workspace, probe_summary),
        },
        "outputs": {
            "refine_brief": relpath(workspace, out_dir / "refine_brief.md"),
            "feedback_summary": relpath(workspace, out_dir / "feedback_summary.md"),
            "metadata_update_reference": relpath(workspace, out_dir / "metadata_update_reference.md"),
            "evidence_manifest": relpath(workspace, out_dir / "evidence_manifest.json"),
        },
        "feedback_count": len(records),
        "profile_column_count": len(columns),
    }
    write_brief(out_dir / "refine_brief.md", manifest_payload)
    write_json(out_dir / "evidence_manifest.json", manifest_payload)

    print(json.dumps({"success": True, "refine_id": refine_id, "output_dir": str(out_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
