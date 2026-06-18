#!/usr/bin/env python3
"""Validate analysis_plan.md for required structure.

Usage:
  python3 validate_plan.py --session-id <SESSION_ID>
  python3 validate_plan.py --plan-file <path>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def find_workspace(start: Path) -> Path:
    env_root = os.environ.get("ANALYST_WORKSPACE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()
    for candidate in (start, *start.parents):
        if (candidate / "schemas").is_dir() and (candidate / "skills").is_dir():
            return candidate
    raise RuntimeError(f"Cannot find RealAnalyst workspace from {start}")


WORKSPACE = find_workspace(Path(__file__).resolve())
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

try:
    from runtime import job_manifest as JOB_MANIFEST_HELPER
except ImportError:
    JOB_MANIFEST_HELPER = None

REQUIRED_CHAPTERS = [
    "需求解析",
    "参数确认",
    "数据源定位",
    "数据源元数据",
    "业务假设",
    "异常判定标准",
    "下钻路径",
    "分析框架",
    "分析目标",
    "预期输出",
]

REQUIRED_FIELDS = [
    "selected_framework_id",
    "framework_selection_reason",
    "selected_analysis_mode",
    "selected_delivery_mode",
    "selected_report_template",
]


def extract_plan_decision(content: str) -> dict[str, str]:
    decision: dict[str, str] = {}
    for field in REQUIRED_FIELDS + [
        "analysis_mode_selection_reason",
        "delivery_mode_selection_reason",
        "template_selection_reason",
    ]:
        pattern = re.compile(
            rf"(?:\*\*)?{re.escape(field)}(?:\*\*)?\s*[:：]\s*`?([^\n`]+?)`?\s*$",
            flags=re.MULTILINE,
        )
        match = pattern.search(content)
        if match:
            decision[field] = match.group(1).strip()
    return decision


def _job_dir_from_plan(plan_path: Path) -> Path | None:
    parts = plan_path.resolve().parts
    if ".meta" not in parts:
        return None
    meta_index = parts.index(".meta")
    if meta_index == 0:
        return None
    return Path(*parts[:meta_index])


def _register_plan_in_manifest(plan_path: Path, decision: dict[str, str]) -> bool:
    if JOB_MANIFEST_HELPER is None:
        return False
    job_dir = _job_dir_from_plan(plan_path)
    if job_dir is None:
        return False
    JOB_MANIFEST_HELPER.create_manifest(job_dir, job_id=job_dir.name, title=job_dir.name, owner_skill="analysis-run")
    try:
        rel = plan_path.resolve().relative_to(job_dir.resolve()).as_posix()
    except ValueError:
        return False
    artifact_id = "analysis_plan"
    JOB_MANIFEST_HELPER.register_artifact(
        job_dir,
        {
            "id": artifact_id,
            "role": "supporting_evidence",
            "kind": "markdown",
            "display_name": "分析计划",
            "path": rel,
            "producer": "analysis-plan",
            "user_visible": False,
            "internal_only": True,
            "safe_to_archive": False,
            "safe_to_delete": False,
        },
    )
    JOB_MANIFEST_HELPER.update_planning(job_dir, {**decision, "plan_artifact_id": artifact_id})
    return True


def validate_plan(plan_path: Path) -> tuple[bool, list[str], list[str], dict[str, str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not plan_path.exists():
        return False, [f"analysis_plan.md not found: {plan_path}"], [], {}

    content = plan_path.read_text(encoding="utf-8")
    decision = extract_plan_decision(content)

    # Check required chapters (flexible heading match)
    for chapter in REQUIRED_CHAPTERS:
        pattern = re.compile(rf"#{{1,3}}\s+.*{re.escape(chapter)}", re.IGNORECASE)
        if not pattern.search(content):
            errors.append(f"Missing required chapter: {chapter}")

    # Check required fields
    for field in REQUIRED_FIELDS:
        if not decision.get(field):
            errors.append(f"Missing required field: {field}")

    # Check hypothesis count (warn if < 3)
    hypo_matches = re.findall(r"假设\s*\d+|goal-hypo-\d+", content)
    if len(hypo_matches) < 3:
        warnings.append(f"Business hypotheses may be insufficient (found ~{len(hypo_matches)}, expected ≥3)")

    passed = len(errors) == 0
    return passed, errors, warnings, decision


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate analysis_plan.md required structure.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--session-id", help="SESSION_ID to locate jobs/{SESSION_ID}/.meta/analysis_plan.md")
    group.add_argument("--plan-file", help="Direct path to analysis_plan.md")
    parser.add_argument("--update-manifest", action="store_true", help="Register plan artifact and selected decisions into job_manifest.json")
    args = parser.parse_args()

    if args.session_id:
        plan_path = WORKSPACE / "jobs" / args.session_id / ".meta" / "analysis_plan.md"
    else:
        plan_path = Path(args.plan_file).expanduser().resolve()

    passed, errors, warnings, decision = validate_plan(plan_path)
    manifest_updated = False
    if passed and args.update_manifest:
        manifest_updated = _register_plan_in_manifest(plan_path, decision)

    result = {
        "success": passed,
        "plan_file": str(plan_path),
        "decision": decision,
        "manifest_updated": manifest_updated,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
