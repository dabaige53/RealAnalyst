#!/usr/bin/env python3
"""配置查询工具。

返回契约：
- --template / --glossary / --metric / --dimension -> query/type/matches/count
- --framework -> query/type/found/framework 或 query/type/found/available_frameworks

实现说明（按项目约束分隔）：
- SQLite（runtime/registry.db）承载：source registry + metric / dimension / glossary lookup tables
- report_templates / analysis_frameworks / workflow / 长文案不入库，仍从 YAML 读取

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
RUNTIME_DIR = WORKSPACE_ROOT / "runtime"

# Make venv site-packages discoverable when invoked via python3.
lib_dir = WORKSPACE_ROOT / ".venv" / "lib"
site_packages = next((p for p in lib_dir.glob("python*/site-packages") if p.exists()), None)
if site_packages and str(site_packages) not in sys.path:
    sys.path.insert(0, str(site_packages))

if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

yaml = importlib.import_module("yaml")

from runtime_config_store import (  # type: ignore[import-not-found]
    search_dimensions as search_dimensions_index,
    search_glossary as search_glossary_index,
    search_metrics as search_metrics_index,
)

LIST_QUERY_TYPES = {"template", "glossary", "metric", "dimension"}


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


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
    data = load_yaml(RUNTIME_DIR / "report_templates.yaml")
    keyword_lower = keyword.lower()
    matches: list[dict[str, Any]] = []

    templates = data.get("templates", {})
    template_aliases = data.get("template_aliases", {})

    core_templates: dict[str, dict[str, Any]] = {}
    if isinstance(templates, dict):
        for tid, tmpl in templates.items():
            if isinstance(tmpl, dict):
                resolved_id = str(tid or tmpl.get("id") or "")
                if resolved_id:
                    core_templates[resolved_id] = tmpl

    for tid, tmpl in core_templates.items():
        name = str(tmpl.get("name") or "")
        keywords = " ".join(tmpl.get("trigger_keywords") or [])
        if (
            keyword_lower in tid.lower()
            or keyword_lower in name.lower()
            or keyword_lower in keywords.lower()
        ):
            matches.append(
                {
                    "id": tid,
                    "name": tmpl.get("name"),
                    "trigger_keywords": tmpl.get("trigger_keywords", []),
                    "description": tmpl.get("description", ""),
                    "analysis_mode": tmpl.get("analysis_mode"),
                    "delivery_mode": tmpl.get("delivery_mode"),
                    "supported_analysis_modes": tmpl.get("supported_analysis_modes", []),
                    "supported_delivery_modes": tmpl.get("supported_delivery_modes", []),
                    "matched_via": "template",
                }
            )

    if isinstance(template_aliases, dict):
        for alias_id, alias in template_aliases.items():
            if not isinstance(alias, dict):
                continue
            alias_name = str(alias.get("name") or "")
            alias_keywords = " ".join(alias.get("trigger_keywords") or [])
            haystack = " ".join([str(alias_id), alias_name, alias_keywords]).lower()
            if keyword_lower not in haystack:
                continue

            canonical_id = str(alias.get("canonical_template") or "")
            canonical = core_templates.get(canonical_id, {})
            matches.append(
                {
                    "id": canonical_id or alias_id,
                    "name": canonical.get("name") or alias_name,
                    "trigger_keywords": alias.get("trigger_keywords", []),
                    "description": canonical.get("description", ""),
                    "analysis_mode": alias.get("analysis_mode") or canonical.get("analysis_mode"),
                    "delivery_mode": alias.get("delivery_mode") or canonical.get("delivery_mode"),
                    "supported_analysis_modes": canonical.get("supported_analysis_modes", []),
                    "supported_delivery_modes": canonical.get("supported_delivery_modes", []),
                    "matched_via": "template_alias",
                    "matched_alias": alias_id,
                    "matched_alias_name": alias_name,
                    "canonical_template": canonical_id or None,
                    "selection_hint": alias.get("selection_hint", ""),
                }
            )

    return build_list_result(keyword, "template", matches)


def search_framework(name: str) -> dict[str, Any]:
    data = load_yaml(RUNTIME_DIR / "analysis_frameworks.yaml")
    name_lower = name.lower()
    frameworks = data.get("frameworks", {})

    if isinstance(frameworks, dict):
        for fid, finfo in frameworks.items():
            if not isinstance(finfo, dict):
                continue
            fname = str(finfo.get("name") or "")
            fname_en = str(finfo.get("name_en") or "")
            desc = str(finfo.get("description") or "")
            scenarios = " ".join(finfo.get("applicable_scenarios") or [])
            haystack = " ".join([str(fid), fname, fname_en, desc, scenarios]).lower()
            if name_lower == str(fid).lower() or name_lower in haystack:
                return build_framework_hit(
                    name,
                    {
                        "id": fid,
                        "name": finfo.get("name"),
                        "name_en": finfo.get("name_en"),
                        "description": finfo.get("description"),
                        "applicable_scenarios": finfo.get("applicable_scenarios", []),
                        "logic_path": finfo.get("logic_path", []),
                        "goal_template": finfo.get("goal_template", {}),
                        "dimension_type_hints": finfo.get("dimension_type_hints", {}),
                    },
                )

        available = [
            {
                "id": fid,
                "name": f.get("name"),
                "scenarios": f.get("applicable_scenarios", []),
            }
            for fid, f in frameworks.items()
            if isinstance(f, dict)
        ]
        return build_framework_miss(name, available)

    return build_framework_miss(name, [])


# ----------------------------
# SQLite-backed queries (migrated)
# ----------------------------

def search_glossary(keyword: str) -> dict[str, Any]:
    return build_list_result(keyword, "glossary", search_glossary_index(keyword))


def search_metric(keyword: str) -> dict[str, Any]:
    return build_list_result(keyword, "metric", search_metrics_index(keyword))


def search_dimension(keyword: str) -> dict[str, Any]:
    return build_list_result(keyword, "dimension", search_dimensions_index(keyword))


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
