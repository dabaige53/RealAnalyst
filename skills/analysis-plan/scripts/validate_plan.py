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
    "selected_analysis_mode",
    "selected_delivery_mode",
    "selected_report_template",
]


def validate_plan(plan_path: Path) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not plan_path.exists():
        return False, [f"analysis_plan.md not found: {plan_path}"], []

    content = plan_path.read_text(encoding="utf-8")

    # Check required chapters (flexible heading match)
    for chapter in REQUIRED_CHAPTERS:
        pattern = re.compile(rf"#{1,3}\s+.*{re.escape(chapter)}", re.IGNORECASE)
        if not pattern.search(content):
            errors.append(f"Missing required chapter: {chapter}")

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in content:
            errors.append(f"Missing required field: {field}")

    # Check hypothesis count (warn if < 3)
    hypo_matches = re.findall(r"假设\s*\d+|goal-hypo-\d+", content)
    if len(hypo_matches) < 3:
        warnings.append(f"Business hypotheses may be insufficient (found ~{len(hypo_matches)}, expected ≥3)")

    passed = len(errors) == 0
    return passed, errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate analysis_plan.md required structure.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--session-id", help="SESSION_ID to locate jobs/{SESSION_ID}/.meta/analysis_plan.md")
    group.add_argument("--plan-file", help="Direct path to analysis_plan.md")
    args = parser.parse_args()

    if args.session_id:
        plan_path = WORKSPACE / "jobs" / args.session_id / ".meta" / "analysis_plan.md"
    else:
        plan_path = Path(args.plan_file).expanduser().resolve()

    passed, errors, warnings = validate_plan(plan_path)

    result = {
        "success": passed,
        "plan_file": str(plan_path),
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
