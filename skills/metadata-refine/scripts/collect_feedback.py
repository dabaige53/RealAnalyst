#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from _common import append_jsonl, feedback_path, now_iso, read_jsonl, workspace_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record or list metadata feedback for an analysis job.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--list", action="store_true", help="List existing feedback records.")
    parser.add_argument("--issue-type", default="", help="field_definition_unclear, metric_formula_unclear, evidence_missing, yaml_data_mismatch, probe_needed")
    parser.add_argument("--summary", default="", help="Short feedback summary.")
    parser.add_argument("--details", default="")
    parser.add_argument("--dataset-id", default="")
    parser.add_argument("--field", action="append", default=[])
    parser.add_argument("--metric", action="append", default=[])
    parser.add_argument("--source", default="user", choices=("user", "analysis", "report", "profile", "system"))
    parser.add_argument("--severity", default="review", choices=("info", "review", "blocking"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = workspace_path(args.workspace)
    path = feedback_path(workspace, args.session_id)

    if args.list:
        records = read_jsonl(path)
        print(json.dumps({"success": True, "path": str(path), "records": records}, ensure_ascii=False, indent=2))
        return 0

    if not args.summary.strip():
        raise SystemExit("--summary is required unless --list is used")

    record: dict[str, Any] = {
        "recorded_at": now_iso(),
        "job_id": args.session_id,
        "issue_type": args.issue_type.strip() or "metadata_review_needed",
        "summary": args.summary.strip(),
        "details": args.details.strip(),
        "dataset_id": args.dataset_id.strip(),
        "fields": [item for item in args.field if item],
        "metrics": [item for item in args.metric if item],
        "source": args.source,
        "severity": args.severity,
        "recommended_next_skill": "RA:metadata-refine",
    }
    append_jsonl(path, record)
    print(json.dumps({"success": True, "path": str(path), "record": record}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
