#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

def _find_workspace_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "runtime").is_dir() and (candidate / "skills").is_dir():
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE_DIR = _find_workspace_root(Path(__file__).resolve())
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from runtime.tableau.sqlite_store import ensure_store_ready, list_entries, load_spec_by_entry_key, save_spec

MONTH_PATTERN = r"^\d{6}$"
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
SEGMENT_PATTERN = r"^[A-Z]{3}-[A-Z]{3}$"
DIGITS_PATTERN = r"^\d+$"


def sanitize_key(text: str) -> str:
    value = text.strip()
    value = re.sub(r"[\s/（）()]+", "_", value)
    value = value.replace("__", "_")
    return value.strip("_") or text


def infer_kind(field_name: str) -> str:
    if field_name in {"日期"} or (field_name.endswith("日期") and "年月" not in field_name):
        return "date_range"
    if field_name in {"产品", "航程", "代理-IATA航协号"}:
        return "text"
    return "discrete"


def infer_filter_validation(field_name: str, existing: dict[str, Any]) -> dict[str, Any] | None:
    if existing.get("validation"):
        return None

    if field_name == "代理-区域":
        return {"mode": "strict", "allowed_values_file": "enums/agent_office.yaml"}
    if "年月" in field_name:
        return {"mode": "strict", "pattern": MONTH_PATTERN}
    if field_name == "产品":
        return {"mode": "strict", "pattern": SEGMENT_PATTERN}
    if field_name == "代理-IATA航协号":
        return {"mode": "strict", "pattern": DIGITS_PATTERN}
    return None


def infer_parameter_validation(field_name: str, existing: dict[str, Any]) -> dict[str, Any] | None:
    if existing.get("validation"):
        return None

    if "年月" in field_name:
        return {"mode": "strict", "pattern": MONTH_PATTERN}
    if "日期" in field_name or field_name.endswith("开始") or field_name.endswith("结束"):
        return {"mode": "strict", "pattern": DATE_PATTERN}
    return None


def ensure_filter_metadata(item: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    current = dict(item)
    added: list[str] = []
    field_name = str(current.get("tableau_field") or current.get("display_name") or current.get("key") or "").strip()
    if not field_name:
        return current, added

    if not current.get("key"):
        current["key"] = sanitize_key(field_name)
        added.append("key")
    if not current.get("display_name"):
        current["display_name"] = field_name
        added.append("display_name")
    if not current.get("kind"):
        current["kind"] = infer_kind(field_name)
        added.append("kind")
    if not current.get("apply_via"):
        current["apply_via"] = "vf"
        added.append("apply_via")
    if "in_view" not in current:
        current["in_view"] = True
        added.append("in_view")

    validation = infer_filter_validation(field_name, current)
    if validation:
        current["validation"] = validation
        added.append("validation")

    return current, added


def ensure_parameter_metadata(item: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    current = dict(item)
    added: list[str] = []
    field_name = str(current.get("tableau_field") or current.get("display_name") or current.get("key") or "").strip()
    if not field_name:
        return current, added

    if not current.get("key"):
        current["key"] = sanitize_key(field_name)
        added.append("key")
    if not current.get("display_name"):
        current["display_name"] = field_name
        added.append("display_name")

    validation = infer_parameter_validation(field_name, current)
    if validation:
        current["validation"] = validation
        added.append("validation")

    return current, added


def enrich_spec(spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    current = deepcopy(spec)
    report: dict[str, Any] = {
        "display_name": current.get("display_name"),
        "entry_key": current.get("entry_key"),
        "filters": [],
        "parameters": [],
    }

    new_filters: list[dict[str, Any]] = []
    for item in current.get("filters", []):
        if not isinstance(item, dict):
            new_filters.append(item)
            continue
        updated, added = ensure_filter_metadata(item)
        new_filters.append(updated)
        if added:
            field_name = str(updated.get("display_name") or updated.get("tableau_field") or updated.get("key"))
            report["filters"].append({"field": field_name, "added": added})

    new_parameters: list[dict[str, Any]] = []
    for item in current.get("parameters", []):
        if not isinstance(item, dict):
            new_parameters.append(item)
            continue
        updated, added = ensure_parameter_metadata(item)
        new_parameters.append(updated)
        if added:
            field_name = str(updated.get("display_name") or updated.get("tableau_field") or updated.get("key"))
            report["parameters"].append({"field": field_name, "added": added})

    if report["filters"] or report["parameters"]:
        current["filters"] = new_filters
        current["parameters"] = new_parameters
        current["updated"] = datetime.now().strftime("%Y-%m-%d")
        report["changed"] = True
    else:
        report["changed"] = False

    return current, report


def main() -> None:
    parser = argparse.ArgumentParser(description="补齐 Tableau runtime metadata 中缺失的可维护字段")
    parser.add_argument("--all", action="store_true", help="处理所有数据源")
    parser.add_argument("--active-only", action="store_true", help="只处理 active 数据源")
    parser.add_argument("--output", help="写出 JSON 报告")
    args = parser.parse_args()

    if not args.all:
        raise SystemExit("请显式传 --all")

    ensure_store_ready()
    entries = list_entries(active_only=args.active_only)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "active_only": args.active_only,
        "changed_entries": [],
        "unchanged_entries": [],
    }

    for entry in entries:
        key = entry.get("key")
        if not isinstance(key, str) or not key:
            continue
        spec = load_spec_by_entry_key(key) or {}
        if not isinstance(spec, dict) or not spec:
            report["unchanged_entries"].append({"entry_key": key, "reason": "missing_spec"})
            continue
        enriched, item_report = enrich_spec(spec)
        item_report["display_name"] = entry.get("display_name") or item_report.get("display_name")
        if item_report.get("changed"):
            save_spec(enriched)
            report["changed_entries"].append(item_report)
        else:
            report["unchanged_entries"].append({
                "entry_key": key,
                "display_name": entry.get("display_name"),
                "reason": "no_missing_metadata",
            })

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
