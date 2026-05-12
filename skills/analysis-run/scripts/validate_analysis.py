#!/usr/bin/env python3
"""Validate analysis.json against schemas/analysis.schema.json.

Usage:
  python3 validate_analysis.py --session-id <SESSION_ID>
  python3 validate_analysis.py --analysis-json <path>
"""

from __future__ import annotations

import argparse
import json
import os
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


def validate_analysis(analysis_path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if not analysis_path.exists():
        return False, [f"analysis.json not found: {analysis_path}"]

    try:
        data = json.loads(analysis_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    # Required top-level fields
    for field in ("job_id", "dataset_id", "created_at", "findings"):
        if field not in data:
            errors.append(f"Missing required field: {field}")

    findings = data.get("findings", [])
    if not isinstance(findings, list):
        errors.append("findings must be a list")
    elif len(findings) == 0:
        errors.append("findings list is empty — no analysis conclusions recorded")
    else:
        for i, f in enumerate(findings):
            fid = f.get("id", f"findings[{i}]")
            if "claim" not in f:
                errors.append(f"{fid}: missing 'claim'")
            evidence = f.get("evidence", {})
            src = evidence.get("source_file", "")
            if not src:
                errors.append(f"{fid}: evidence.source_file is empty")
            else:
                # Check if source file exists relative to workspace
                job_dir = analysis_path.parent
                candidate = job_dir / src
                if not candidate.exists():
                    # Try workspace-relative
                    candidate2 = WORKSPACE / src
                    if not candidate2.exists():
                        errors.append(f"{fid}: evidence.source_file not found: {src}")
            if "confidence" not in f:
                errors.append(f"{fid}: missing 'confidence'")

    passed = len(errors) == 0
    return passed, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate analysis.json structure and evidence links.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--session-id", help="SESSION_ID to locate jobs/{SESSION_ID}/analysis.json")
    group.add_argument("--analysis-json", help="Direct path to analysis.json")
    args = parser.parse_args()

    if args.session_id:
        analysis_path = WORKSPACE / "jobs" / args.session_id / "analysis.json"
    else:
        analysis_path = Path(args.analysis_json).expanduser().resolve()

    passed, errors = validate_analysis(analysis_path)

    result = {
        "success": passed,
        "analysis_json": str(analysis_path),
        "errors": errors,
        "error_count": len(errors),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
