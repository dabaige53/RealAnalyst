#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIR = bootstrap_workspace_path()
AUDIT_DIR = Path("metadata/audit")
LOG_NAME = "metadata_changes.jsonl"
REPORT_NAME = "metadata_change_report.md"
REFINE_DIFF_DIR = "refine-diffs"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def audit_dir(workspace: Path) -> Path:
    return workspace / AUDIT_DIR


def log_path(workspace: Path) -> Path:
    return audit_dir(workspace) / LOG_NAME


def report_path(workspace: Path) -> Path:
    return audit_dir(workspace) / REPORT_NAME


def refine_diff_dir(workspace: Path) -> Path:
    return audit_dir(workspace) / REFINE_DIFF_DIR


def normalize_relpath(workspace: Path, value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    path = Path(raw).expanduser()
    if not path.is_absolute():
        return raw
    try:
        return str(path.relative_to(workspace))
    except ValueError:
        return str(path)


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def read_text_if_exists(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def resolve_path(workspace: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return workspace / path


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|")


def write_refine_diff_report(
    workspace: Path,
    *,
    refine_id: str,
    changed_paths: list[str],
    before_paths: list[str],
    summary: str,
) -> str:
    safe_refine_id = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in refine_id).strip("-") or "refine"
    out_dir = refine_diff_dir(workspace)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_refine_id}-{datetime.now(timezone.utc).astimezone().strftime('%Y%m%d-%H%M%S')}.md"
    lines = [
        "# Refine Metadata YAML Diff",
        "",
        f"- generated_at: {now_iso()}",
        f"- refine_id: {refine_id}",
        f"- summary: {summary}",
        "",
    ]

    for index, changed in enumerate(changed_paths):
        before = before_paths[index] if index < len(before_paths) else ""
        changed_path = resolve_path(workspace, changed)
        before_path = resolve_path(workspace, before) if before else None
        before_text = read_text_if_exists(before_path) if before_path else ""
        after_text = read_text_if_exists(changed_path)
        diff = difflib.unified_diff(
            before_text.splitlines(),
            after_text.splitlines(),
            fromfile=before or f"{changed} (before missing)",
            tofile=changed,
            lineterm="",
        )
        lines.extend([f"## {changed}", ""])
        if before:
            lines.append(f"- before: {before}")
        lines.append(f"- after: {changed}")
        lines.extend(["", "```diff", *diff, "```", ""])

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return normalize_relpath(workspace, str(out_path))


def append_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def render_report(records: list[dict[str, Any]]) -> str:
    lines = [
        "# Metadata Change Report",
        "",
        f"- generated_at: {now_iso()}",
        f"- change_count: {len(records)}",
        f"- log_file: metadata/audit/{LOG_NAME}",
        "",
        "## Latest Changes",
        "",
    ]
    if not records:
        lines.append("No metadata changes have been recorded yet.")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| time | type | summary | paths | datasets | evidence |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for record in reversed(records[-50:]):
        paths = "<br>".join(record.get("paths") or [])
        datasets = "<br>".join(record.get("dataset_ids") or [])
        evidence_items = list(record.get("evidence") or [])
        if record.get("diff_report"):
            evidence_items.append(str(record.get("diff_report")))
        evidence = "<br>".join(evidence_items)
        lines.append(
            "| {time} | {kind} | {summary} | {paths} | {datasets} | {evidence} |".format(
                time=record.get("recorded_at") or "",
                kind=record.get("change_type") or "",
                summary=markdown_escape(str(record.get("summary") or "")),
                paths=markdown_escape(paths),
                datasets=markdown_escape(datasets),
                evidence=markdown_escape(evidence),
            )
        )

    lines.extend(["", "## Full Record Details", ""])
    for idx, record in enumerate(reversed(records), start=1):
        lines.extend(
            [
                f"### {idx}. {record.get('summary') or 'metadata change'}",
                "",
                f"- recorded_at: {record.get('recorded_at') or ''}",
                f"- change_type: {record.get('change_type') or ''}",
                f"- actor: {record.get('actor') or ''}",
                f"- paths: {', '.join(record.get('paths') or [])}",
                f"- dataset_ids: {', '.join(record.get('dataset_ids') or [])}",
                f"- refine_id: {record.get('refine_id') or ''}",
                f"- evidence: {', '.join(record.get('evidence') or [])}",
                f"- diff_report: {record.get('diff_report') or ''}",
                f"- details: {record.get('details') or ''}",
                "",
            ]
        )
    return "\n".join(lines)


def write_report(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(records), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record and report metadata maintenance changes.")
    parser.add_argument("--workspace", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser("record", help="Append a metadata maintenance record.")
    record.add_argument("--summary", required=True)
    record.add_argument("--change-type", default="maintenance")
    record.add_argument("--path", action="append", default=[])
    record.add_argument("--before", action="append", default=[], help="Before-copy path for changed YAML. Repeat in the same order as --path.")
    record.add_argument("--dataset-id", action="append", default=[])
    record.add_argument("--refine-id", default="")
    record.add_argument("--evidence", action="append", default=[])
    record.add_argument("--details", default="")
    record.add_argument("--actor", default="llm")

    subparsers.add_parser("report", help="Regenerate the metadata change report from the JSONL log.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    log_file = log_path(workspace)
    report_file = report_path(workspace)

    if args.command == "record":
        paths = [normalize_relpath(workspace, item) for item in args.path if item.strip()]
        before_paths = [normalize_relpath(workspace, item) for item in args.before if item.strip()]
        diff_report = ""
        if args.refine_id.strip():
            if not before_paths:
                raise SystemExit("--before is required when --refine-id is provided so a YAML diff report can be generated")
            diff_report = write_refine_diff_report(
                workspace,
                refine_id=args.refine_id.strip(),
                changed_paths=paths,
                before_paths=before_paths,
                summary=args.summary.strip(),
            )

        record = {
            "recorded_at": now_iso(),
            "change_type": args.change_type.strip() or "maintenance",
            "summary": args.summary.strip(),
            "details": args.details.strip(),
            "actor": args.actor.strip() or "llm",
            "paths": paths,
            "before_paths": before_paths,
            "dataset_ids": [item.strip() for item in args.dataset_id if item.strip()],
            "refine_id": args.refine_id.strip(),
            "evidence": [normalize_relpath(workspace, item) for item in args.evidence if item.strip()],
            "diff_report": diff_report,
        }
        append_record(log_file, record)
        records = read_records(log_file)
        write_report(report_file, records)
        print(
            json.dumps(
                {
                    "success": True,
                    "record": record,
                    "log": str(log_file),
                    "report": str(report_file),
                    "change_count": len(records),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "report":
        records = read_records(log_file)
        write_report(report_file, records)
        print(
            json.dumps(
                {
                    "success": True,
                    "log": str(log_file),
                    "report": str(report_file),
                    "change_count": len(records),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
