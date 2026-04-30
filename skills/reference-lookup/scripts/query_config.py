#!/usr/bin/env python3
"""Reference lookup tool.

返回契约：
- --template / --glossary / --metric / --dimension -> query/type/matches/count
- --framework -> query/type/found/framework 或 query/type/found/available_frameworks

实现说明（按项目约束分隔）：
- metadata index 承载 metric / dimension / glossary lookup
- template / framework 查询只提供轻量 reference hints

边界说明：
- 数据源查询使用 query_registry.py，不属于本脚本的输出契约
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()


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


WORKSPACE_ROOT = _find_workspace_root(SCRIPT_PATH)
METADATA_INDEX_DIR = WORKSPACE_ROOT / "metadata" / "index"
REPORT_TEMPLATE_REFERENCE = WORKSPACE_ROOT / "skills" / "report" / "references" / "template-system-v2.md"

# Make venv site-packages discoverable when invoked via python3.
lib_dir = WORKSPACE_ROOT / ".venv" / "lib"
site_packages = next((p for p in lib_dir.glob("python*/site-packages") if p.exists()), None)
if site_packages and str(site_packages) not in sys.path:
    sys.path.insert(0, str(site_packages))

yaml = importlib.import_module("yaml")

LIST_QUERY_TYPES = {"template", "glossary", "metric", "dimension"}


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def search_jsonl(path: Path, keyword: str) -> list[dict[str, Any]]:
    keyword_lower = keyword.lower()
    matches = []
    for row in load_jsonl(path):
        haystack = json.dumps(row, ensure_ascii=False).lower()
        if keyword_lower in haystack:
            matches.append(row)
    return matches[:20]


def build_list_result(query: str, query_type: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
    if query_type not in LIST_QUERY_TYPES:
        raise ValueError(f"unsupported list query type: {query_type}")
    return {"query": query, "type": query_type, "matches": matches, "count": len(matches)}


def build_framework_hit(query: str, framework: dict[str, Any]) -> dict[str, Any]:
    return {"query": query, "type": "framework", "found": True, "framework": framework}


def build_framework_miss(query: str, available_frameworks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "query": query,
        "type": "framework",
        "found": False,
        "available_frameworks": available_frameworks,
    }


# ----------------------------
# YAML-backed queries (do NOT migrate)
# ----------------------------

def search_template(keyword: str) -> dict[str, Any]:
    keyword_lower = keyword.lower()
    matches: list[dict[str, Any]] = []
    if REPORT_TEMPLATE_REFERENCE.exists():
        for line in REPORT_TEMPLATE_REFERENCE.read_text(encoding="utf-8").splitlines():
            if keyword_lower in line.lower():
                matches.append({"matched_via": "template_reference", "source": str(REPORT_TEMPLATE_REFERENCE), "line": line.strip()})
                if len(matches) >= 20:
                    break

    return build_list_result(keyword, "template", matches)


def search_framework(name: str) -> dict[str, Any]:
    return build_framework_miss(
        name,
        [
            {"id": "monitoring", "name": "经营监控", "scenarios": ["trend", "alert", "routine report"]},
            {"id": "diagnosis", "name": "问题诊断", "scenarios": ["root cause", "variance"]},
            {"id": "benchmark", "name": "对标分析", "scenarios": ["ranking", "comparison"]},
        ],
    )


# ----------------------------
# SQLite-backed queries (migrated)
# ----------------------------

def search_glossary(keyword: str) -> dict[str, Any]:
    return build_list_result(keyword, "glossary", search_jsonl(METADATA_INDEX_DIR / "terms.jsonl", keyword))


def search_metric(keyword: str) -> dict[str, Any]:
    return build_list_result(keyword, "metric", search_jsonl(METADATA_INDEX_DIR / "metrics.jsonl", keyword))


def search_dimension(keyword: str) -> dict[str, Any]:
    return build_list_result(keyword, "dimension", search_jsonl(METADATA_INDEX_DIR / "fields.jsonl", keyword))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="查询 runtime 中的模板、术语、指标、框架与维度定义。",
        epilog=(
            "Datasource 查询请使用 "
            "python3 {baseDir}/runtime/tableau/query_registry.py --search <关键词>；"
            "该命令不属于本脚本的输出契约。"
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--template", "-t", help="搜索报告模板")
    group.add_argument("--glossary", "-g", help="搜索术语")
    group.add_argument("--metric", "-m", help="搜索指标")
    group.add_argument("--framework", "-f", help="查询分析框架（返回完整配置含 logic_path）")
    group.add_argument("--dimension", "-d", help="搜索维度定义")

    args = parser.parse_args()

    if args.template:
        result = search_template(args.template)
    elif args.glossary:
        result = search_glossary(args.glossary)
    elif args.metric:
        result = search_metric(args.metric)
    elif args.framework:
        result = search_framework(args.framework)
    elif args.dimension:
        result = search_dimension(args.dimension)
    else:
        parser.print_help()
        raise SystemExit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
