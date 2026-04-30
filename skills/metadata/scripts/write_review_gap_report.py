#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_io import load_dataset_file, resolve_dataset_path  # noqa: E402


def _text(value: Any) -> str:
    return str(value or "").strip()


def write_report(workspace: Path, dataset_ids: list[str], output: Path) -> Path:
    lines = ["# DuckDB Metadata 待确认字段清单", ""]
    for dataset_id in dataset_ids:
        dataset = load_dataset_file(resolve_dataset_path(workspace, dataset_id))
        lines.append(f"## {dataset.get('display_name')} `{dataset_id}`")
        lines.append("")
        rows: list[tuple[str, str, str, str]] = []
        for section in ("fields", "metrics"):
            for item in dataset.get(section) or []:
                if not isinstance(item, dict):
                    continue
                definition = item.get("business_definition") if isinstance(item.get("business_definition"), dict) else {}
                if definition.get("source_type") != "pending":
                    continue
                rows.append(
                    (
                        "字段" if section == "fields" else "指标",
                        _text(item.get("display_name") or item.get("name")),
                        _text(item.get("source_field") or item.get("physical_name")),
                        _text(definition.get("text") or "业务定义待确认"),
                    )
                )
        if not rows:
            lines.append("- 无待确认字段或指标。")
            lines.append("")
            continue
        lines.append("| 类型 | 展示名 | 源字段 | 当前业务定义 |")
        lines.append("| --- | --- | --- | --- |")
        for kind, display_name, source_field, definition_text in rows:
            escaped_definition = definition_text.replace("|", r"\|")
            lines.append(f"| {kind} | {display_name} | `{source_field}` | {escaped_definition} |")
        lines.append("")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a Markdown review-gap report for pending metadata definitions.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--dataset-id", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    path = write_report(workspace, args.dataset_id, Path(args.output).expanduser().resolve())
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
