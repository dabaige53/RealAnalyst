#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_workspace_path

WORKSPACE_DIR = bootstrap_workspace_path()

from runtime.tableau.sqlite_store import list_entries, load_spec_by_entry_key  # noqa: E402


def default_report_dir() -> Path:
    return WORKSPACE_DIR / "metadata" / "sync" / "duckdb" / "reports"


def build_report_filename(source_id: str, *, generated_at: datetime) -> str:
    timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{source_id}_sync_report.md"


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_list_dicts(value: Any) -> list[dict[str, Any]]:
    return [x for x in _safe_list(value) if isinstance(x, dict)]


def _safe_list_str(value: Any) -> list[str]:
    return [str(x) for x in _safe_list(value) if isinstance(x, str) and x]


def _load_targets(*, key: str | None, all_entries: bool) -> list[dict[str, Any]]:
    entries = [e for e in list_entries(active_only=not all_entries) if isinstance(e, dict) and e.get("source_backend") == "duckdb"]
    if key:
        return [e for e in entries if e.get("key") == key]
    if all_entries:
        return entries
    return []


def render_sync_report(
    *,
    entry: dict[str, Any],
    spec: dict[str, Any],
    generated_at: datetime,
    report_dir: Path,
    sync_mode: str,
    step_results: dict[str, str],
) -> str:
    duckdb_meta = entry.get("duckdb") if isinstance(entry.get("duckdb"), dict) else {}
    semantics = entry.get("semantics") if isinstance(entry.get("semantics"), dict) else {}
    dimensions = _safe_list_dicts(spec.get("dimensions"))
    measures = _safe_list_dicts(spec.get("measures"))
    filters = _safe_list_dicts(spec.get("filters"))

    lines: list[str] = []
    lines.append("# DuckDB Sync Report")
    lines.append("")
    lines.append("## 1. 同步任务概览")
    lines.append("")
    lines.append("- 报告类型：DuckDB 元数据注册/同步明细报告")
    lines.append(f"- 报告生成时间：{generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 同步对象：`{entry.get('source_id', '')}`")
    lines.append(f"- 显示名称：`{entry.get('display_name', '')}`")
    lines.append(f"- 默认报告目录：`{report_dir}`")
    lines.append("- 本次执行链路：" + " → ".join(f"`{x}`" for x in ["register", "sync_registry", "validate", "generate_sync_report"]))
    lines.append(f"- 同步模式：`{sync_mode}`")
    lines.append(
        "- 步骤状态："
        + f" register={step_results.get('register', 'unknown')},"
        + f" registry={step_results.get('registry', 'unknown')},"
        + f" validate={step_results.get('validate', 'unknown')}"
    )
    lines.append("")

    lines.append("## 2. 数据源注册信息")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    lines.append(f"| `source_id` | `{entry.get('source_id', '')}` |")
    lines.append(f"| `key` | `{entry.get('key', '')}` |")
    lines.append(f"| `type` | `{entry.get('type', '')}` |")
    lines.append(f"| `status` | `{entry.get('status', '')}` |")
    lines.append(f"| `category` | `{entry.get('category', '')}` |")
    lines.append(f"| `display_name` | `{entry.get('display_name', '')}` |")
    lines.append(f"| `description` | `{entry.get('description', '')}` |")
    lines.append(f"| `db_path` | `{duckdb_meta.get('db_path', '')}` |")
    lines.append(f"| `schema` | `{duckdb_meta.get('schema', '')}` |")
    lines.append(f"| `object_name` | `{duckdb_meta.get('object_name', '')}` |")
    lines.append(f"| `object_kind` | `{duckdb_meta.get('object_kind', '')}` |")
    lines.append("")

    lines.append("## 3. 本次写入摘要")
    lines.append("")
    lines.append(f"- 字段总数：`{len(_safe_list_str(entry.get('fields')))}`")
    lines.append(f"- 维度数：`{len(dimensions)}`")
    lines.append(f"- 指标数：`{len(measures)}`")
    lines.append(f"- 筛选器数：`{len(filters)}`")
    lines.append(f"- 粒度字段数：`{len(_safe_list_str(semantics.get('grain')))}`")
    lines.append(f"- 时间字段数：`{len(_safe_list_str(semantics.get('time_fields')))}`")
    lines.append("")

    lines.append("## 4. 语义层明细")
    lines.append("")
    lines.append("### 4.1 粒度")
    lines.append("")
    for item in _safe_list_str(semantics.get("grain")) or ["未配置"]:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("### 4.2 时间字段")
    lines.append("")
    for item in _safe_list_str(semantics.get("time_fields")) or ["未配置"]:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("### 4.3 适用场景")
    lines.append("")
    for item in _safe_list_str(semantics.get("suitable_for")) or ["未配置"]:
        lines.append(f"- `{item}`")
    lines.append("")
    lines.append("### 4.4 不适用场景")
    lines.append("")
    for item in _safe_list_str(semantics.get("not_suitable_for")) or ["未配置"]:
        lines.append(f"- `{item}`")
    lines.append("")

    lines.append("## 5. 字段明细")
    lines.append("")
    lines.append("### 5.1 维度")
    lines.append("")
    if dimensions:
        lines.append("| 字段 | 类型 |")
        lines.append("| --- | --- |")
        for item in dimensions:
            lines.append(f"| `{item.get('name', '')}` | `{item.get('data_type', '')}` |")
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("### 5.2 指标")
    lines.append("")
    if measures:
        lines.append("| 字段 | 类型 |")
        lines.append("| --- | --- |")
        for item in measures:
            lines.append(f"| `{item.get('name', '')}` | `{item.get('data_type', '')}` |")
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("### 5.3 筛选器")
    lines.append("")
    if filters:
        lines.append("| 字段 | 显示名 | 应用方式 |")
        lines.append("| --- | --- | --- |")
        for item in filters:
            lines.append(
                f"| `{item.get('key', '')}` | `{item.get('display_name', '')}` | `{item.get('apply_via', '')}` |"
            )
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("## 6. 校验结果")
    lines.append("")
    if step_results.get("validate") == "success":
        lines.append("- 本次注册校验通过，可供后续 `data-export` 使用。")
    elif step_results.get("validate") == "failed":
        lines.append("- 本次注册已落库，但校验失败，需要先修正 registry/spec 后再用于正式导出。")
    else:
        lines.append("- 本次未执行正式校验。")
    lines.append("")

    return "\n".join(lines) + "\n"


def write_report(
    *,
    entry: dict[str, Any],
    spec: dict[str, Any],
    report_dir: Path,
    generated_at: datetime,
    sync_mode: str,
    step_results: dict[str, str],
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    filename = build_report_filename(str(entry.get("source_id") or entry.get("key") or "unknown"), generated_at=generated_at)
    report_path = report_dir / filename
    report_path.write_text(
        render_sync_report(
            entry=entry,
            spec=spec,
            generated_at=generated_at,
            report_dir=report_dir,
            sync_mode=sync_mode,
            step_results=step_results,
        ),
        encoding="utf-8",
    )
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DuckDB sync Markdown reports")
    parser.add_argument("--key", help="Generate report for a specific entry key")
    parser.add_argument("--all", action="store_true", help="Generate reports for all active DuckDB entries")
    parser.add_argument("--report-dir", help="Output directory for Markdown reports")
    parser.add_argument("--sync-mode", choices=["live", "dry-run"], default="live")
    parser.add_argument("--register-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--registry-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--validate-step-status", choices=["success", "failed", "skipped"], default="success")
    args = parser.parse_args()

    if not args.key and not args.all:
        print("[Error] Specify --key KEY or --all")
        raise SystemExit(2)

    targets = _load_targets(key=args.key, all_entries=args.all)
    if not targets:
        print("[WARN] No entries matched")
        return

    generated_at = datetime.now().astimezone()
    report_dir = Path(args.report_dir).expanduser().resolve() if args.report_dir else default_report_dir()
    step_results = {
        "register": args.register_step_status,
        "registry": args.registry_step_status,
        "validate": args.validate_step_status,
    }

    for entry in targets:
        key = str(entry.get("key") or "")
        spec = load_spec_by_entry_key(key) or {}
        report_path = write_report(
            entry=entry,
            spec=spec,
            report_dir=report_dir,
            generated_at=generated_at,
            sync_mode=args.sync_mode,
            step_results=step_results,
        )
        print(f"[OK] report -> {report_path}")


if __name__ == "__main__":
    main()
