#!/usr/bin/env python3
"""Append-only report update helper for continuous-analysis jobs.

What it does:
- Find or create the job report file (optional)
- Ensure timeline sections exist: "## 需求时间线" and "## 报告更新时间线"
- Append one bullet to each timeline for this round
- Append a new markdown block at the end (append-only)
- Refresh "## 输出文件清单" by scanning job directory (excludes data/, profile/, .meta/, and audit/system files)
- Optionally append to .meta/user_request_timeline.md and .meta/analysis_journal.md

This script is intentionally conservative: it never deletes existing report content.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _find_workspace_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "runtime").is_dir() and (candidate / "skills").is_dir():
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE_DIR = _find_workspace_root(Path(__file__).resolve())


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _now_human() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")


def _resolve_session_id(session_id: str | None) -> str:
    sid = (session_id or "").strip()
    if not sid:
        import os

        sid = (os.environ.get("SESSION_ID") or "").strip()
    if not sid:
        raise SystemExit("SESSION_ID_REQUIRED")
    return sid


def _job_dir(session_id: str) -> Path:
    jobs = WORKSPACE_DIR / "jobs" / session_id
    legacy = WORKSPACE_DIR / "temp" / session_id
    if legacy.exists() and not jobs.exists():
        return legacy
    return jobs


def _meta_dir(session_id: str) -> Path:
    return _job_dir(session_id) / ".meta"


def _relpath(path: Path) -> str:
    if path.is_absolute():
        try:
            return str(path.relative_to(WORKSPACE_DIR))
        except ValueError:
            return str(path)
    return str(path)


def _load_meta_artifact_index(session_id: str) -> dict[str, Any] | None:
    p = _meta_dir(session_id) / "artifact_index.json"
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _pick_report_path(session_id: str, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)

    idx = _load_meta_artifact_index(session_id)
    if idx:
        for item in idx.get("items", []) or []:
            if isinstance(item, dict) and item.get("kind") == "report" and item.get("path"):
                return WORKSPACE_DIR / str(item["path"])

    # Legacy root summary
    legacy = _job_dir(session_id) / "artifact_index.json"
    if legacy.exists():
        try:
            payload = json.loads(legacy.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("report"), str):
                return WORKSPACE_DIR / payload["report"]
        except Exception:
            pass

    # Fallback: find latest report file
    job = _job_dir(session_id)
    candidates = sorted(job.glob("报告_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _ensure_section(text: str, heading: str) -> str:
    if heading in text:
        return text

    # Insert after the first markdown title if present, otherwise at top.
    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines[:40]):
        if line.startswith("# "):
            insert_at = i + 1
            break
    block = ["", heading, "", "- {ts}: （待补充）".format(ts=_now_human()), ""]
    new_lines = lines[:insert_at] + block + lines[insert_at:]
    return "\n".join(new_lines).rstrip() + "\n"


def _append_bullet_under_heading(text: str, heading: str, bullet: str) -> str:
    """Append a bullet inside a level-2 heading section.

    Safety requirements:
    - Must not delete any existing content.
    - Must be append-only (adds a new bullet line).
    """

    if heading not in text:
        text = _ensure_section(text, heading)

    bullet_line = f"- {bullet}".strip()
    if bullet_line in text:
        return text

    m = re.search(rf"(?m)^{re.escape(heading)}\s*$", text)
    if not m:
        # Fallback: append to end (still append-only)
        return text.rstrip() + "\n" + bullet_line + "\n"

    start = m.end()
    rest = text[start:]
    m2 = re.search(r"(?m)^##\s+[^\n]+$", rest)
    end = start + (m2.start() if m2 else len(rest))

    section = text[start:end]
    new_section = section.rstrip() + "\n" + bullet_line + "\n\n"

    return text[:start] + new_section + text[end:]


def _scan_output_files(job_dir: Path) -> tuple[list[str], list[str]]:
    """Return (analysis_products, raw_data) as workspace-relative paths."""

    analysis_products: list[str] = []
    raw_data: list[str] = []

    # Analysis products: root-level md/csv/docx/xlsx/pptx
    for ext in ("*.md", "*.csv", "*.docx", "*.xlsx", "*.pptx"):
        for p in job_dir.glob(ext):
            name = p.name
            if name in {"artifact_index.json", "export_summary.json", "duckdb_export_summary.json"}:
                continue
            analysis_products.append(_relpath(p))

    # Raw data: data/*.csv
    data_dir = job_dir / "data"
    if data_dir.exists():
        for p in data_dir.glob("*.csv"):
            raw_data.append(_relpath(p))

    analysis_products = sorted(set(analysis_products))
    raw_data = sorted(set(raw_data))
    return analysis_products, raw_data


def _refresh_output_file_list(text: str, job_dir: Path) -> str:
    heading = "## 输出文件清单"
    analysis_products, raw_data = _scan_output_files(job_dir)

    block_lines = [heading, "", "### 分析产物(可交付)"]
    if analysis_products:
        block_lines += [f"- {p}" for p in analysis_products]
    else:
        block_lines += ["- （暂无）"]

    block_lines += ["", "### 原始数据(仅存档)"]
    if raw_data:
        block_lines += [f"- {p}" for p in raw_data]
    else:
        block_lines += ["- （暂无）"]

    block = "\n".join(block_lines).rstrip() + "\n"

    if heading not in text:
        return text.rstrip() + "\n\n" + block

    # Replace existing section content
    pattern = re.compile(r"^## 输出文件清单\s*$", re.M)
    m = pattern.search(text)
    if not m:
        return text.rstrip() + "\n\n" + block

    start = m.start()
    rest = text[m.end() :]
    # Find next level-2 heading
    m2 = re.search(r"\n## (?!输出文件清单)[^\n]+\n", rest)
    if m2:
        end = m.end() + m2.start()
        return text[:start].rstrip() + "\n\n" + block + text[end:]
    # To end of file
    return text[:start].rstrip() + "\n\n" + block


def _append_to_meta_md(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# {title}\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"- {_now_human()}: {body.strip()}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Append-only report update")
    ap.add_argument("--session-id", default="", help="jobs/<session-id>/ (defaults to env SESSION_ID)")
    ap.add_argument("--report-path", default="", help="Explicit report path")
    ap.add_argument("--init-if-missing", action="store_true", help="Create a minimal report if none exists")
    ap.add_argument("--title", default="报告（持续更新）", help="Title for report init")

    ap.add_argument("--request", default="", help="One-line user request summary for timelines")
    ap.add_argument("--update", default="", help="One-line report update summary for timelines")

    ap.add_argument("--append-file", default="", help="Markdown file to append to report")
    ap.add_argument("--append-text", default="", help="Markdown text to append to report")
    ap.add_argument("--append-title", default="追加分析", help="Heading title for appended block")

    ap.add_argument("--refresh-file-list", action="store_true", help="Refresh output file list section")
    ap.add_argument("--update-meta-md", action="store_true", help="Also append into .meta/*.md timelines")

    args = ap.parse_args()

    session_id = _resolve_session_id(args.session_id)
    job = _job_dir(session_id)
    job.mkdir(parents=True, exist_ok=True)
    meta = _meta_dir(session_id)
    meta.mkdir(parents=True, exist_ok=True)

    report_path = _pick_report_path(session_id, args.report_path.strip() or None)
    if report_path is None:
        if not args.init_if_missing:
            raise SystemExit("REPORT_NOT_FOUND")
        # init minimal report in job root
        report_path = job / "报告_持续更新.md"
        if not report_path.exists():
            report_path.write_text(f"# {args.title}\n\n", encoding="utf-8")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not report_path.exists():
        if not args.init_if_missing:
            raise SystemExit("REPORT_NOT_FOUND")
        report_path.write_text(f"# {args.title}\n\n", encoding="utf-8")

    text = report_path.read_text(encoding="utf-8")

    # Ensure timeline sections exist
    text = _ensure_section(text, "## 需求时间线")
    text = _ensure_section(text, "## 报告更新时间线")

    if args.request.strip():
        text = _append_bullet_under_heading(text, "## 需求时间线", f"{_now_human()}：{args.request.strip()}")

    if args.update.strip():
        text = _append_bullet_under_heading(text, "## 报告更新时间线", f"{_now_human()}：{args.update.strip()}")

    append_body = ""
    if args.append_file:
        append_body = Path(args.append_file).read_text(encoding="utf-8")
    elif args.append_text:
        # Allow passing a single argument with literal "\\n" sequences.
        append_body = args.append_text
        if "\\n" in append_body and "\n" not in append_body:
            append_body = append_body.replace("\\n", "\n")

    if append_body.strip():
        block = (
            "\n\n---\n\n"
            + f"## {args.append_title}（{_now_human()}）\n\n"
            + append_body.strip()
            + "\n"
        )
        text = text.rstrip() + block

    if args.refresh_file_list:
        text = _refresh_output_file_list(text, job)

    report_path.write_text(text.rstrip() + "\n", encoding="utf-8")

    # Optional meta md updates
    if args.update_meta_md:
        if args.request.strip():
            _append_to_meta_md(meta / "user_request_timeline.md", "user request timeline", args.request)
        if args.update.strip():
            _append_to_meta_md(meta / "analysis_journal.md", "analysis journal", args.update)

    # Ensure report is indexed (best-effort, no hard dependency)
    try:
        meta_index = meta / "artifact_index.json"
        if meta_index.exists():
            payload = json.loads(meta_index.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                items = payload.get("items")
                if not isinstance(items, list):
                    items = []
                    payload["items"] = items
                rp = _relpath(report_path)
                found = False
                for it in items:
                    if isinstance(it, dict) and it.get("path") == rp:
                        it["kind"] = it.get("kind") or "report"
                        it["role"] = it.get("role") or "user"
                        it["updated_at"] = _now_iso()
                        found = True
                        break
                if not found:
                    items.append({"path": rp, "kind": "report", "role": "user", "created_at": _now_iso()})
                payload["updated_at"] = _now_iso()
                meta_index.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    print(
        json.dumps(
            {
                "session_id": session_id,
                "report_path": _relpath(report_path),
                "updated_at": _now_iso(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
