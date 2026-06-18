#!/usr/bin/env python3
"""Analysis reference lookup tool.

返回契约：
- --template -> query/type/matches/count
- --framework -> query/type/found/framework 或 query/type/found/available_frameworks

边界说明：
- 本脚本只覆盖 template 和 framework 两类查询
- metric / field / term 查询请使用 RA:metadata-search
- datasource 查询请使用 query_registry.py
"""

from __future__ import annotations

import argparse
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


def _resolve_skill_file(*parts: str) -> Path:
    candidates = [
        WORKSPACE_ROOT / "skills" / Path(*parts),
        WORKSPACE_ROOT / ".agents" / "skills" / Path(*parts),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


REPORT_TEMPLATE_REFERENCE = _resolve_skill_file("report", "references", "template-system-v2.md")
FRAMEWORK_REFERENCE = _resolve_skill_file("analysis-reference", "references", "analysis-frameworks.json")

# Make venv site-packages discoverable when invoked via python3.
lib_dir = WORKSPACE_ROOT / ".venv" / "lib"
site_packages = next((p for p in lib_dir.glob("python*/site-packages") if p.exists()), None)
if site_packages and str(site_packages) not in sys.path:
    sys.path.insert(0, str(site_packages))


def build_list_result(query: str, query_type: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
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


def load_frameworks() -> list[dict[str, Any]]:
    if not FRAMEWORK_REFERENCE.exists():
        return []
    payload = json.loads(FRAMEWORK_REFERENCE.read_text(encoding="utf-8"))
    frameworks = payload.get("frameworks") if isinstance(payload, dict) else payload
    if not isinstance(frameworks, list):
        return []
    return [framework for framework in frameworks if isinstance(framework, dict)]


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
    query = name.strip().lower()
    frameworks = load_frameworks()
    for framework in frameworks:
        searchable = {
            str(framework.get("id", "")).lower(),
            str(framework.get("name", "")).lower(),
            str(framework.get("name_en", "")).lower(),
            str(framework.get("name_cn", "")).lower(),
            *[str(alias).lower() for alias in framework.get("aliases", [])],
        }
        if query in searchable:
            return build_framework_hit(name, framework)

    for framework in frameworks:
        searchable = {
            *[str(mode).lower() for mode in framework.get("analysis_modes", [])],
            *[str(scenario).lower() for scenario in framework.get("applicable_scenarios", [])],
            *[str(scenario).lower() for scenario in framework.get("best_for", [])],
        }
        if query in searchable:
            return build_framework_hit(name, framework)

    available = [
        {
            "id": framework["id"],
            "name": framework["name"],
            "aliases": framework.get("aliases", []),
            "scenarios": framework.get("applicable_scenarios", []),
        }
        for framework in frameworks
    ]
    return build_framework_miss(name, available)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="查询报告模板和分析框架（RA:analysis-reference）。",
        epilog=(
            "metric / field / term 查询请使用 RA:metadata-search；"
            "datasource 查询请使用 python3 {baseDir}/runtime/tableau/query_registry.py。"
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--template", "-t", help="搜索报告模板")
    group.add_argument("--framework", "-f", help="查询分析框架（返回完整配置含 logic_path）")

    args = parser.parse_args()

    if args.template:
        result = search_template(args.template)
    elif args.framework:
        result = search_framework(args.framework)
    else:
        parser.print_help()
        raise SystemExit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
