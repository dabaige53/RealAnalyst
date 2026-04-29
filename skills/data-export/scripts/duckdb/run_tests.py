#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

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


WORKSPACE_DIR = _find_workspace_root(Path(__file__).resolve())
EXPORTER = (
    WORKSPACE_DIR / "skills" / "data-export" / "scripts" / "duckdb" / "export_duckdb_source.py"
    if (WORKSPACE_DIR / "skills" / "data-export" / "scripts" / "duckdb" / "export_duckdb_source.py").exists()
    else WORKSPACE_DIR / ".agents" / "skills" / "data-export" / "scripts" / "duckdb" / "export_duckdb_source.py"
)
PY = WORKSPACE_DIR / "scripts" / "py"
TEST_SESSION = "data-export-duckdb-tests"


def run_case(name: str, args: list[str], expect_success: bool) -> dict:
    proc = subprocess.run(
        [str(PY), str(EXPORTER), *args],
        cwd=WORKSPACE_DIR,
        text=True,
        capture_output=True,
    )
    passed = (proc.returncode == 0) if expect_success else (proc.returncode != 0)
    return {
        "name": name,
        "expect_success": expect_success,
        "returncode": proc.returncode,
        "passed": passed,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run DuckDB registry export smoke cases")
    parser.add_argument("--session-id", default=TEST_SESSION, help="测试输出使用的 session_id")
    parser.add_argument("--result-file", help="结果 JSON 输出路径；默认写入 jobs/<session_id>/")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = [
        run_case(
            "select_export_ok",
            [
                "--source-id", "duckdb.example.orders",
                "--session-id", args.session_id,
                "--select", "order_date,order_id,region,revenue",
                "--limit", "10",
                "--output-name", "duckdb_select_ok.csv",
            ],
            True,
        ),
        run_case(
            "aggregate_export_ok",
            [
                "--source-id", "duckdb.example.forecast",
                "--session-id", args.session_id,
                "--group-by", "forecast_date,product_category",
                "--aggregate", "forecast_revenue:sum:forecast_revenue_total",
                "--order-by", "forecast_date:asc",
                "--limit", "10",
                "--output-name", "duckdb_agg_ok.csv",
            ],
            True,
        ),
        run_case(
            "invalid_field_blocked",
            [
                "--source-id", "duckdb.example.forecast",
                "--session-id", args.session_id,
                "--select", "不存在字段",
                "--output-name", "bad_invalid_field.csv",
            ],
            False,
        ),
        run_case(
            "invalid_source_blocked",
            [
                "--source-id", "duckdb.example.scratch",
                "--session-id", args.session_id,
                "--output-name", "bad_invalid_source.csv",
            ],
            False,
        ),
        run_case(
            "invalid_aggregate_blocked",
            [
                "--source-id", "duckdb.example.forecast",
                "--session-id", args.session_id,
                "--group-by", "forecast_date",
                "--aggregate", "forecast_revenue:median:median_revenue",
                "--output-name", "bad_invalid_agg.csv",
            ],
            False,
        ),
        run_case(
            "aggregate_with_select_blocked",
            [
                "--source-id", "duckdb.example.forecast",
                "--session-id", args.session_id,
                "--select", "日期",
                "--aggregate", "forecast_revenue:sum:forecast_revenue_total",
                "--output-name", "bad_select_mix.csv",
            ],
            False,
        ),
    ]

    summary = {
        "success": all(c["passed"] for c in cases),
        "passed": sum(1 for c in cases if c["passed"]),
        "failed": sum(1 for c in cases if not c["passed"]),
        "cases": cases,
    }
    out_path = (
        Path(args.result_file).expanduser().resolve()
        if args.result_file
        else WORKSPACE_DIR / "jobs" / args.session_id / "duckdb_export_test_results.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"result_file": str(out_path), **{k: summary[k] for k in ["success", "passed", "failed"]}},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
