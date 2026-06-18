#!/usr/bin/env python3
"""Render a user-facing analysis-run reply from job_manifest.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _find_workspace_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        has_skills = (candidate / "skills").is_dir() or (candidate / ".agents" / "skills").is_dir()
        if (candidate / "runtime").is_dir() and has_skills:
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE_DIR = _find_workspace_root(Path(__file__).resolve())
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from runtime import job_manifest


def _clean_lines(values: list[Any]) -> list[str]:
    return [str(value).strip() for value in values if str(value or "").strip()]


def _deliverable_line(artifact: dict[str, Any], *, technical: bool) -> str:
    name = str(artifact.get("display_name") or artifact.get("id") or "交付物").strip()
    if technical:
        return f"- {name}: {artifact.get('path')}"
    return f"- {name}"


def render_reply(job_dir: str | Path, *, technical: bool = False) -> str:
    payload = job_manifest.load_manifest(job_dir)
    user_surface = payload["user_surface"]
    deliverables = job_manifest.user_visible_artifacts(job_dir)

    lines: list[str] = []
    summary = str(user_surface.get("summary") or "").strip()
    if summary:
        lines.append(summary)
    else:
        lines.append("本轮分析任务已更新。")

    if deliverables:
        lines.extend(["", "可查看的交付物："])
        lines.extend(_deliverable_line(artifact, technical=technical) for artifact in deliverables)

    verification_status = str(user_surface.get("verification_status") or "not_run")
    if verification_status != "not_run":
        status_text = {
            "passed": "验证已通过。",
            "warning": "验证有提醒，结论可用但需要留意风险。",
            "failed": "验证未通过，需要先修正后再交付。",
        }.get(verification_status, f"验证状态：{verification_status}")
        lines.extend(["", status_text])

    risks = _clean_lines(user_surface.get("risks") or [])
    if risks:
        lines.extend(["", "需要留意："])
        lines.extend(f"- {risk}" for risk in risks)

    next_actions = _clean_lines(user_surface.get("next_actions") or [])
    if next_actions:
        lines.extend(["", "下一步："])
        lines.extend(f"- {action}" for action in next_actions)

    return "\n".join(lines).strip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a business-facing reply from a job manifest.")
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--technical", action="store_true", help="Include internal relative paths for technical review.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown text.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        text = render_reply(args.job_dir, technical=args.technical)
        if args.json:
            print(json.dumps({"success": True, "reply": text}, ensure_ascii=False, indent=2))
        else:
            print(text, end="")
        return 0
    except Exception as exc:
        error_code = getattr(exc, "error_code", "RENDER_USER_REPLY_FAILED")
        print(json.dumps({"success": False, "error": str(exc), "error_code": error_code}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
