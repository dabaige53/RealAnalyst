#!/usr/bin/env python3
"""
验证器 - 零幻觉门禁

验证规则：
1. 证据链完整性：每个 finding 必须有 evidence
2. 排名一致性：Top/Bottom 声明与 statistics 对齐
3. 趋势方向一致性：增长/下降与 trend_label 对齐
4. 数字可追溯性：报告中数字必须能映射到 analysis.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

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


WORKSPACE_ROOT = _find_workspace_root(Path(__file__).resolve())
LIB_DIR = WORKSPACE_ROOT / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))
from log_utils import log as base_log  # type: ignore


def log(output_dir: str, msg: str) -> None:
    base_log(output_dir, "Verify", msg)


def check_evidence_completeness(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = []

    for finding in findings:
        finding_id = finding.get("id", "unknown")
        evidence = finding.get("evidence", {})

        check: dict[str, Any] = {
            "check_id": f"ev_{finding_id}",
            "check_type": "evidence_completeness",
            "finding_id": finding_id,
            "target": finding.get("title", "")[:50],
            "status": "passed",
            "details": {},
        }

        has_calculation = bool(evidence.get("calculation"))
        has_row_indices = bool(evidence.get("row_indices"))

        check["details"]["has_calculation"] = has_calculation
        check["details"]["has_row_indices"] = has_row_indices

        if not has_calculation:
            check["status"] = "warning"
            check["message"] = "缺少 calculation 字段"

        if finding.get("type") in ("ranking", "trend", "comparison") and not has_row_indices:
            if check["status"] == "passed":
                check["status"] = "warning"
                check["message"] = "缺少 row_indices 追溯"
            else:
                check["message"] += "; 缺少 row_indices 追溯"

        checks.append(check)

    return checks


def check_ranking_consistency(
    findings: list[dict[str, Any]], statistics: dict[str, Any]
) -> list[dict[str, Any]]:
    checks = []

    ranking_findings = [f for f in findings if f.get("type") == "ranking"]

    for finding in ranking_findings:
        finding_id = finding.get("id", "unknown")
        title = finding.get("title", "")
        insight = finding.get("insight", "")

        check: dict[str, Any] = {
            "check_id": f"rk_{finding_id}",
            "check_type": "ranking_consistency",
            "finding_id": finding_id,
            "target": title[:50],
            "status": "passed",
            "details": {},
        }

        top_match = re.search(r"(\w+)\s*的.*最高", insight) or re.search(r"(\w+)\s*.*领先", insight)

        if top_match:
            claimed_top = top_match.group(1)
            check["details"]["claimed_top"] = claimed_top

            actual_top = None
            # 改进：根据 finding 的内容匹配最相关的统计项
            relevant_stat = None
            if "人数" in insight or "客运" in insight:
                relevant_stat = statistics.get("rank_airline_people")
            elif "单位收入" in insight or "座收" in insight:
                relevant_stat = statistics.get("rank_airline_revenue")

            if relevant_stat:
                top_items = relevant_stat.get("top_items", [])
                if top_items:
                    actual_top = top_items[0].get("name", "")
            else:
                # 兜底：取第一个统计项
                for stat in statistics.values():
                    top_items = stat.get("top_items", [])
                    if top_items:
                        actual_top = top_items[0].get("name", "")
                        break

            check["details"]["actual_top"] = actual_top

            if actual_top and claimed_top != actual_top:
                check["status"] = "failed"
                check["message"] = f"排名声明不一致：报告称 {claimed_top} 最高，实际是 {actual_top}"

        checks.append(check)

    return checks


def check_trend_consistency(
    findings: list[dict[str, Any]], statistics: dict[str, Any]
) -> list[dict[str, Any]]:
    checks = []

    trend_findings = [f for f in findings if f.get("type") in ("trend", "comparison")]

    for finding in trend_findings:
        finding_id = finding.get("id", "unknown")
        insight = finding.get("insight", "")

        check: dict[str, Any] = {
            "check_id": f"tr_{finding_id}",
            "check_type": "trend_consistency",
            "finding_id": finding_id,
            "target": finding.get("title", "")[:50],
            "status": "passed",
            "details": {},
        }

        claimed_direction = None
        if any(kw in insight for kw in ["增长", "上升", "增加", "提升"]):
            claimed_direction = "up"
        elif any(kw in insight for kw in ["下降", "下滑", "减少", "下跌"]):
            claimed_direction = "down"
        elif any(kw in insight for kw in ["平稳", "持平", "稳定"]):
            claimed_direction = "flat"

        check["details"]["claimed_direction"] = claimed_direction

        actual_direction = None
        for stat in statistics.values():
            if stat.get("trend_label"):
                actual_direction = stat["trend_label"]
                break
            if stat.get("delta_pct") is not None:
                delta = stat["delta_pct"]
                if delta > 5:
                    actual_direction = "up"
                elif delta < -5:
                    actual_direction = "down"
                else:
                    actual_direction = "flat"
                break

        check["details"]["actual_direction"] = actual_direction

        if claimed_direction and actual_direction and claimed_direction != actual_direction:
            check["status"] = "failed"
            check["message"] = (
                f"趋势方向不一致：报告称 {claimed_direction}，实际是 {actual_direction}"
            )

        checks.append(check)

    return checks


def check_numeric_traceability(
    report: str, analysis: dict[str, Any], df: pd.DataFrame
) -> list[dict[str, Any]]:
    checks = []
    findings = analysis.get("findings", [])
    statistics = analysis.get("statistics", {})

    numbers_in_report = re.findall(r"[\d,]+(?:\.\d+)?", report)
    large_numbers: list[float] = []

    for num_str in numbers_in_report:
        try:
            num = float(num_str.replace(",", ""))
            if num > 100:
                large_numbers.append(num)
        except ValueError:
            pass

    unique_numbers = list(set(large_numbers))[:15]

    for num in unique_numbers:
        check: dict[str, Any] = {
            "check_id": f"num_{int(num)}",
            "check_type": "numeric_traceability",
            "target": f"{num:,.2f}",
            "status": "passed",
            "details": {"traced_to": None},
        }

        found = False
        source = None

        for op_id, stat in statistics.items():
            if found:
                break

            if stat.get("total") and abs(float(stat["total"]) - num) < 1:
                found = True
                source = f"statistics.{op_id}.total"
                break

            for item in stat.get("top_items", []):
                if abs(float(item.get("value", 0)) - num) < 1:
                    found = True
                    source = f"statistics.{op_id}.top_items"
                    break

            for item in stat.get("items", []):
                if abs(float(item.get("value", 0)) - num) < 1:
                    found = True
                    source = f"statistics.{op_id}.items"
                    break

        if not found:
            for finding in findings:
                evidence = finding.get("evidence", {})
                for val in evidence.values():
                    if isinstance(val, (int, float)) and abs(val - num) < 1:
                        found = True
                        source = f"finding.{finding.get('id')}.evidence"
                        break
                if found:
                    break

        if not found:
            for col in df.select_dtypes(include=["int64", "float64"]).columns:
                col_sum = df[col].sum()
                col_mean = df[col].mean()
                col_max = df[col].max()
                col_min = df[col].min()

                if abs(col_sum - num) < 1:
                    found = True
                    source = f"data.{col}.sum"
                    break
                if abs(col_mean - num) < 0.1:
                    found = True
                    source = f"data.{col}.mean"
                    break
                if abs(col_max - num) < 0.1 or abs(col_min - num) < 0.1:
                    found = True
                    source = f"data.{col}.extreme"
                    break

        check["details"]["traced_to"] = source

        if not found and num > 1000:
            check["status"] = "failed"
            check["message"] = f"数字 {num:,.0f} 无法追溯到数据源"

        checks.append(check)

    return checks


def check_confidence_threshold(
    findings: list[dict[str, Any]], threshold: float = 0.7
) -> list[dict[str, Any]]:
    checks = []

    low_confidence = [f for f in findings if f.get("confidence", 1.0) < threshold]

    if low_confidence:
        check: dict[str, Any] = {
            "check_id": "conf_001",
            "check_type": "confidence_threshold",
            "target": f"{len(low_confidence)} findings below {threshold}",
            "status": "warning",
            "message": f"有 {len(low_confidence)} 条发现置信度低于 {threshold}",
            "details": {"low_confidence_ids": [f.get("id") for f in low_confidence]},
        }
        checks.append(check)

    return checks


def check_metric_definition_appendix(report: str) -> list[dict[str, Any]]:
    """检查报告是否包含“本次新增/临时口径说明”章节与最小表格列。"""

    required_header = "## 口径说明（本次新增/临时）"
    checks: list[dict[str, Any]] = []

    header_present = required_header in report
    table_present = bool(re.search(r"\|\s*名称\s*\|.*业务含义.*计算逻辑.*来源\s*\|", report))

    check: dict[str, Any] = {
        "check_id": "md_001",
        "check_type": "metric_definition_appendix",
        "target": required_header,
        "status": "passed",
        "details": {"header_present": header_present, "table_present": table_present},
    }

    if not header_present:
        check["status"] = "failed"
        check["message"] = (
            "报告缺少口径说明附录章节。建议在报告末尾增加："
            "\n- 标题：## 口径说明（本次新增/临时）"
            "\n- 表格列：名称｜业务含义｜计算逻辑｜来源"
        )
    elif not table_present:
        check["status"] = "failed"
        check["message"] = (
            "口径说明章节存在，但未检测到包含最小列的口径表格（名称/业务含义/计算逻辑/来源）。"
        )

    checks.append(check)
    return checks


def check_metric_term_consistency(report: str, df: pd.DataFrame) -> list[dict[str, Any]]:
    """检查报告指标命名是否与数据字段一致，避免子集指标误写成总量。"""

    checks: list[dict[str, Any]] = []
    data_columns = set(map(str, df.columns))

    check: dict[str, Any] = {
        "check_id": "mt_001",
        "check_type": "metric_term_consistency",
        "target": "订单量术语一致性",
        "status": "passed",
        "details": {
            "uses_ticket_term": "订单量" in report,
            "has_ticket_measure": "订单量" in data_columns,
            "has_foreigner_ticket_measure": "外国人乘机_订单量" in data_columns,
        },
    }

    if "订单量" not in report:
        checks.append(check)
        return checks

    has_explicit_alias_mapping = bool(
        re.search(r"订单量（\s*外国人乘机_?订单量(?:口径)?\s*）", report)
        or re.search(r"订单量（\s*口径[:：]?\s*外国人乘机_?订单量\s*）", report)
        or re.search(
            r"\|\s*订单量(?:（[^|]+）)?\s*\|[^|]*\|[^|]*外国人乘机_?订单量[^|]*\|",
            report,
        )
    )

    check["details"]["has_explicit_alias_mapping"] = has_explicit_alias_mapping

    # 报告使用“订单量”，但数据中没有同名字段、只有外籍客票字段时，必须披露映射关系。
    if "订单量" not in data_columns and "外国人乘机_订单量" in data_columns:
        if not has_explicit_alias_mapping:
            check["status"] = "failed"
            check["message"] = (
                "报告使用“订单量”术语，但数据源无同名指标，仅有“外国人乘机_订单量”。"
                "请在口径说明中明确映射关系，或将正文统一改为“外国人乘机订单量”。"
            )

    checks.append(check)
    return checks


def check_data_source_section_position(report: str) -> list[dict[str, Any]]:
    """检查“数据来源”章节是否位于报告上方（H2前两段内）。"""

    checks: list[dict[str, Any]] = []
    h2_matches = list(re.finditer(r"^##\s+(.+?)\s*$", report, flags=re.MULTILINE))

    check: dict[str, Any] = {
        "check_id": "ds_001",
        "check_type": "data_source_section_position",
        "target": "## 数据来源",
        "status": "passed",
        "details": {
            "total_h2_sections": len(h2_matches),
            "data_source_h2_index": None,
        },
    }

    data_source_index = None
    for idx, match in enumerate(h2_matches):
        title = match.group(1).strip()
        if title.startswith("数据来源"):
            data_source_index = idx
            break

    check["details"]["data_source_h2_index"] = data_source_index

    if data_source_index is None:
        check["status"] = "failed"
        check["message"] = (
            "报告缺少“## 数据来源”章节。请在报告上方补充数据源、筛选条件、数据行数和采集时间。"
        )
    elif data_source_index > 1:
        check["status"] = "failed"
        check["message"] = (
            "“数据来源”章节位置过后。请将“## 数据来源”移动到报告上方（建议位于前两个 H2 章节内），"
            "再进入总量/结构/归因分析。"
        )

    checks.append(check)
    return checks


def _looks_like_system_source_key(token: str) -> bool:
    value = token.strip()
    if not value:
        return False
    if re.search(r"[\u4e00-\u9fff]", value):
        return False
    if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        return False
    return "." in value or "_" in value


def check_data_source_display_name(report: str) -> list[dict[str, Any]]:
    """检查数据源展示是否误用系统英文标识（source_key）。"""

    checks: list[dict[str, Any]] = []
    source_related_lines = [
        line.strip()
        for line in report.splitlines()
        if ("数据源" in line or "数据来源" in line) and line.strip()
    ]

    check: dict[str, Any] = {
        "check_id": "ds_002",
        "check_type": "data_source_display_name",
        "target": "数据源展示中文化",
        "status": "passed",
        "details": {"matched_tokens": []},
    }

    matched_tokens: list[str] = []
    for line in source_related_lines:
        for token in re.findall(r"`([^`]+)`", line):
            if _looks_like_system_source_key(token):
                matched_tokens.append(token)
        for token in re.findall(r"[（(]([^()（）]+)[）)]", line):
            if _looks_like_system_source_key(token):
                matched_tokens.append(token)

    check["details"]["matched_tokens"] = sorted(set(matched_tokens))

    if matched_tokens:
        check["status"] = "failed"
        check["message"] = (
            "数据源展示包含系统英文标识（source_key）。请仅保留中文数据源名称，"
            "不要在报告中展示 sales.agent、market.xx 等系统命名。"
        )

    checks.append(check)
    return checks


def check_output_file_list_section(report: str) -> list[dict[str, Any]]:
    """检查报告是否包含“输出文件清单”章节。"""

    checks: list[dict[str, Any]] = []
    has_section = bool(re.search(r"^#{2,3}\s+输出文件清单\s*$", report, flags=re.MULTILINE))

    check: dict[str, Any] = {
        "check_id": "of_001",
        "check_type": "output_file_list_section",
        "target": "## 输出文件清单",
        "status": "passed",
        "details": {"section_present": has_section},
    }

    if not has_section:
        check["status"] = "failed"
        check["message"] = "报告缺少“输出文件清单”章节。请补充分析产物与原始数据清单。"

    checks.append(check)
    return checks


def verify_report(
    csv_path: str, analysis_path: str, report_path: str, output_dir: str
) -> dict[str, Any]:
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    log(output_dir, "[Verify] 开始验证")

    df = pd.read_csv(csv_path, encoding="utf-8")
    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)
    with open(report_path, encoding="utf-8") as f:
        report = f.read()

    job_id = os.environ.get("SESSION_ID", Path(output_dir).name)
    findings = analysis.get("findings", [])
    statistics = analysis.get("statistics", {})
    if not isinstance(statistics, dict):
        statistics = {}

    log(output_dir, f"[Verify] 数据: {len(df)} 行, 分析: {len(findings)} 条发现")

    all_checks: list[dict[str, Any]] = []

    evidence_checks = check_evidence_completeness(findings)
    all_checks.extend(evidence_checks)
    log(output_dir, f"[Verify] 证据链检查: {len(evidence_checks)} 项")

    ranking_checks = check_ranking_consistency(findings, statistics)
    all_checks.extend(ranking_checks)
    log(output_dir, f"[Verify] 排名一致性检查: {len(ranking_checks)} 项")

    trend_checks = check_trend_consistency(findings, statistics)
    all_checks.extend(trend_checks)
    log(output_dir, f"[Verify] 趋势方向检查: {len(trend_checks)} 项")

    numeric_checks = check_numeric_traceability(report, analysis, df)
    all_checks.extend(numeric_checks)
    log(output_dir, f"[Verify] 数字追溯检查: {len(numeric_checks)} 项")

    confidence_checks = check_confidence_threshold(findings)
    all_checks.extend(confidence_checks)

    appendix_checks = check_metric_definition_appendix(report)
    all_checks.extend(appendix_checks)
    log(output_dir, f"[Verify] 口径说明附录检查: {len(appendix_checks)} 项")

    metric_term_checks = check_metric_term_consistency(report, df)
    all_checks.extend(metric_term_checks)
    log(output_dir, f"[Verify] 指标命名一致性检查: {len(metric_term_checks)} 项")

    data_source_position_checks = check_data_source_section_position(report)
    all_checks.extend(data_source_position_checks)
    log(output_dir, f"[Verify] 数据来源章节位置检查: {len(data_source_position_checks)} 项")

    data_source_display_checks = check_data_source_display_name(report)
    all_checks.extend(data_source_display_checks)
    log(output_dir, f"[Verify] 数据源中文展示检查: {len(data_source_display_checks)} 项")

    output_file_list_checks = check_output_file_list_section(report)
    all_checks.extend(output_file_list_checks)
    log(output_dir, f"[Verify] 输出文件清单章节检查: {len(output_file_list_checks)} 项")

    passed = sum(1 for c in all_checks if c["status"] == "passed")
    failed = sum(1 for c in all_checks if c["status"] == "failed")
    warnings = sum(1 for c in all_checks if c["status"] == "warning")

    if failed > 0:
        status = "failed"
    elif warnings > 0:
        status = "warning"
    else:
        status = "passed"

    verification = {
        "job_id": job_id,
        "verified_at": datetime.now().isoformat(),
        "status": status,
        "checks": all_checks,
        "summary": {
            "total_checks": len(all_checks),
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
        },
        "check_categories": {
            "evidence_completeness": len(evidence_checks),
            "ranking_consistency": len(ranking_checks),
            "trend_consistency": len(trend_checks),
            "numeric_traceability": len(numeric_checks),
            "confidence_threshold": len(confidence_checks),
            "metric_definition_appendix": len(appendix_checks),
            "metric_term_consistency": len(metric_term_checks),
            "data_source_section_position": len(data_source_position_checks),
            "data_source_display_name": len(data_source_display_checks),
            "output_file_list_section": len(output_file_list_checks),
        },
    }

    verification_path = Path(output_dir) / "verification.json"
    with open(verification_path, "w", encoding="utf-8") as f:
        json.dump(verification, f, ensure_ascii=False, indent=2)

    log(output_dir, f"[Verify] 验证完成: {status.upper()}")
    log(output_dir, f"[Verify] 通过: {passed}, 失败: {failed}, 警告: {warnings}")

    if status == "failed":
        failed_checks = [c for c in all_checks if c["status"] == "failed"]
        for fc in failed_checks:
            log(output_dir, f"[Error] {fc.get('check_type')}: {fc.get('message', '')}")

    return {
        "success": status != "failed",
        "status": status,
        "verification_path": str(verification_path),
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="验证报告中的声明是否有数据支撑，并输出 verification.json 与标准 JSON 摘要。"
    )
    parser.add_argument("data_csv", help="原始数据文件路径")
    parser.add_argument("analysis_json", help="分析结果 JSON 路径")
    parser.add_argument("report_md", help="待验证报告路径")
    parser.add_argument("output_dir", help="输出目录，将写入 verification.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    result = verify_report(args.data_csv, args.analysis_json, args.report_md, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
