#!/usr/bin/env python3
"""High-level profiling wrapper with automatic CSV resolution."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from profile import profile_data  # type: ignore[import-not-found]


def _find_workspace_root(start: Path) -> Path:
    env_root = os.environ.get("ANALYST_WORKSPACE_DIR")
    if env_root:
        return Path(env_root).expanduser().resolve()

    for candidate in [start.parent, *start.parents]:
        if (candidate / "runtime").is_dir() and (
            (candidate / ".agents" / "skills").is_dir() or (candidate / "skills").is_dir()
        ):
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


def _workspace_dir() -> Path:
    return _find_workspace_root(Path(__file__).resolve())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="自动解析正式 CSV 并生成 profile/manifest.json 与 profile/profile.json。",
    )
    parser.add_argument("--data-csv", help="显式指定输入 CSV；传入后不再读取 export_summary.json")
    parser.add_argument("--output-dir", help="输出目录；默认使用 jobs/{SESSION_ID}")
    return parser


def _emit(payload: dict[str, Any], *, exit_code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def _error(message: str, *, error_code: str, extra: dict[str, Any] | None = None) -> int:
    payload: dict[str, Any] = {
        "success": False,
        "error": message,
        "error_code": error_code,
    }
    if extra:
        payload.update(extra)
    return _emit(payload, exit_code=1)


def _resolve_output_dir(raw_output_dir: str | None) -> Path:
    if raw_output_dir:
        return Path(raw_output_dir).expanduser().resolve()

    session_id = os.environ.get("SESSION_ID")
    if not session_id:
        raise ValueError("missing SESSION_ID; pass --output-dir or export SESSION_ID")

    workspace_dir = _workspace_dir()
    jobs_dir = (workspace_dir / "jobs" / session_id).resolve()
    return jobs_dir


def _resolve_data_csv_from_summary(output_dir: Path) -> tuple[Path, str]:
    export_summary_path = output_dir / "export_summary.json"
    if export_summary_path.exists():
        try:
            payload = json.loads(export_summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"export_summary.json is invalid JSON: {export_summary_path}") from exc

        if not isinstance(payload, dict):
            raise ValueError("export_summary.json must be a JSON object")

        raw_views = payload.get("views")
        if not isinstance(raw_views, list):
            raise ValueError("export_summary.json missing views list")

        candidates: list[Path] = []
        for item in raw_views:
            if not isinstance(item, dict):
                continue
            if item.get("status") != "success":
                continue
            file_path = item.get("file_path")
            if not isinstance(file_path, str) or not file_path:
                continue
            candidate = (output_dir / file_path).resolve()
            try:
                candidate.relative_to(output_dir.resolve())
            except ValueError as exc:
                raise ValueError(f"file_path escapes output_dir: {file_path}") from exc
            candidates.append(candidate)

        if not candidates:
            raise ValueError("no successful CSV candidates found in export_summary.json")
        if len(candidates) > 1:
            raise RuntimeError("multiple successful CSV candidates found in export_summary.json")
        return candidates[0], "export_summary"

    duckdb_summary_path = output_dir / "duckdb_export_summary.json"
    if duckdb_summary_path.exists():
        try:
            payload = json.loads(duckdb_summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"duckdb_export_summary.json is invalid JSON: {duckdb_summary_path}") from exc

        if not isinstance(payload, dict):
            raise ValueError("duckdb_export_summary.json must be a JSON object")
        file_path = payload.get("output_file")
        if not isinstance(file_path, str) or not file_path:
            raise ValueError("duckdb_export_summary.json missing output_file")
        candidate = (_workspace_dir() / file_path).resolve()
        try:
            candidate.relative_to(_workspace_dir().resolve())
        except ValueError as exc:
            raise ValueError(f"output_file escapes workspace: {file_path}") from exc
        return candidate, "duckdb_export_summary"

    raise FileNotFoundError(
        f"neither export_summary.json nor duckdb_export_summary.json found in: {output_dir}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        output_dir = _resolve_output_dir(args.output_dir)
    except ValueError as exc:
        return _error(str(exc), error_code="OUTPUT_DIR_REQUIRED")

    output_dir.mkdir(parents=True, exist_ok=True)

    if args.data_csv:
        data_csv = Path(args.data_csv).expanduser().resolve()
        resolved_from = "explicit"
    else:
        try:
            data_csv, resolved_from = _resolve_data_csv_from_summary(output_dir)
        except FileNotFoundError as exc:
            return _error(str(exc), error_code="EXPORT_SUMMARY_NOT_FOUND")
        except RuntimeError as exc:
            return _error(
                str(exc),
                error_code="MULTIPLE_CSV_CANDIDATES",
                extra={"output_dir": str(output_dir)},
            )
        except ValueError as exc:
            return _error(
                str(exc),
                error_code="EXPORT_SUMMARY_INVALID",
                extra={"output_dir": str(output_dir)},
            )

    if not data_csv.exists():
        return _error(
            f"data_csv not found: {data_csv}",
            error_code="DATA_CSV_NOT_FOUND",
            extra={"output_dir": str(output_dir), "data_csv": str(data_csv)},
        )

    log_buffer = io.StringIO()
    with redirect_stdout(log_buffer):
        result = profile_data(str(data_csv), str(output_dir))
    result["data_csv"] = str(data_csv)
    result["output_dir"] = str(output_dir)
    result["resolved_from"] = resolved_from
    return _emit(result, exit_code=0)


if __name__ == "__main__":
    raise SystemExit(main())
