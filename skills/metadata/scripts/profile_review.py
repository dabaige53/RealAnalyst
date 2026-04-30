#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_completeness import (
    completeness_findings,
    load_dataset_mappings,
    profile_columns,
    text,
)
from skills.metadata.lib.metadata_io import MetadataError, load_dataset_file, resolve_dataset_path


def now_stamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")


def read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_path(workspace: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else workspace / path


def resolve_refine_profile(workspace: Path, refine_id: str) -> tuple[Path | None, dict[str, Any]]:
    if not refine_id:
        return None, {}
    refine_dir = workspace / "metadata" / "sources" / "refine" / refine_id
    candidates = [refine_dir / "data_probe.json", refine_dir / "profile.json", refine_dir / "evidence_manifest.json"]
    for candidate in candidates:
        payload = read_json(candidate)
        if payload:
            return candidate, payload
    return None, {}


def relpath(workspace: Path, path: Path) -> str:
    try:
        return str(path.relative_to(workspace))
    except ValueError:
        return str(path)


def render_markdown(payload: dict[str, Any]) -> str:
    findings = payload["findings"]
    lines = [
        "# Metadata Profile Review",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- dataset_id: {payload['dataset_id']}",
        f"- profile_source: {payload.get('profile_source') or 'not provided'}",
        f"- profile_column_count: {payload['profile_column_count']}",
        "",
        "## 应补指标",
        "",
    ]
    if findings["should_add_metrics"]:
        lines.extend(["| field | display_name | role | type | reason |", "| --- | --- | --- | --- | --- |"])
        for item in findings["should_add_metrics"]:
            lines.append(
                f"| {item['field']} | {item['display_name']} | {item['role']} | {item['type']} | {item['reason']} |"
            )
    else:
        lines.append("- 未发现 metric-like 字段漏注册为 dataset metrics。")

    lines.extend(["", "## 待人工确认", ""])
    review_items = [*findings["mapping_gaps"], *findings["needs_review"]]
    if review_items:
        lines.extend(["| target | reason | detail |", "| --- | --- | --- |"])
        for item in review_items:
            target = item.get("field") or item.get("view_field") or item.get("mapping_id") or "dataset"
            detail = item.get("sample_source") or item.get("standard_id") or ""
            lines.append(f"| {target} | {item.get('reason') or ''} | {detail} |")
    else:
        lines.append("- 未发现 mapping、sample_profile 或枚举证据缺口。")

    lines.extend(["", "## 不建议注册为指标", ""])
    if findings["not_metric"]:
        lines.extend(["| field | display_name | reason |", "| --- | --- | --- |"])
        for item in findings["not_metric"]:
            lines.append(f"| {item['field']} | {item['display_name']} | {item['reason']} |")
    else:
        lines.append("- 没有字段显式声明 `not_metric_reason`。")

    lines.extend(
        [
            "",
            "## Next Step",
            "",
            "- 本报告只给出维护建议，不自动修改 YAML。",
            "- 确认后用 `RA:metadata` 更新 dataset metrics、mapping 和字段 evidence，再运行 `metadata validate --completeness`。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Review dataset metadata completeness against profile/refine evidence.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--profile-json", default="")
    parser.add_argument("--refine-id", default="")
    parser.add_argument("--output-dir", default="metadata/audit/profile-review")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    try:
        dataset_path = resolve_dataset_path(workspace, args.dataset_id)
        dataset = load_dataset_file(dataset_path)
    except MetadataError as exc:
        raise SystemExit(str(exc)) from exc

    profile_path = resolve_path(workspace, args.profile_json)
    profile = read_json(profile_path)
    if not profile:
        profile_path, profile = resolve_refine_profile(workspace, args.refine_id.strip())

    mappings = load_dataset_mappings(workspace, text(dataset.get("id")))
    findings = completeness_findings(dataset, mappings=mappings)
    profile_source = relpath(workspace, profile_path) if profile_path else ""
    output_dir = resolve_path(workspace, args.output_dir) or (workspace / "metadata" / "audit" / "profile-review")
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{text(dataset.get('id')).replace('/', '_')}-{now_stamp()}"
    payload = {
        "success": True,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "dataset_id": text(dataset.get("id")),
        "dataset_path": relpath(workspace, dataset_path),
        "profile_source": profile_source,
        "profile_column_count": len(profile_columns(profile)),
        "mapping_count": len(mappings),
        "findings": findings,
        "summary": {key: len(value) for key, value in findings.items()},
    }
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    payload["outputs"] = {"json": relpath(workspace, json_path), "markdown": relpath(workspace, md_path)}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
