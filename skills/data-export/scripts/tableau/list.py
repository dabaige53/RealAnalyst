#!/usr/bin/env python3
from __future__ import annotations

"""
Tableau Views List Script

List available views on Tableau Server.

Usage:
    python list.py [filter]

Example:
    python list.py            # List all views
    python list.py "销售"     # Filter views containing "销售"
"""

import argparse
import json
import sys
from typing import Any

import requests

from auth import get_auth


def list_views(name_filter: str | None = None) -> list[dict[str, Any]]:
    """List available Tableau views.

    Args:
        name_filter: Optional filter string for view names.

    Returns:
        List of view info dicts.
    """
    auth = get_auth()

    try:
        auth.signin()
    except Exception as e:
        print(f"[Error] 认证失败: {e}", file=sys.stderr)
        return []

    try:
        views_url = f"{auth.api_base}/views?pageSize=1000"
        print(f"[Tableau] 获取视图列表...")

        resp = requests.get(views_url, headers=auth.get_headers(), timeout=60)
        resp.raise_for_status()

        views = resp.json().get("views", {}).get("view", [])
        print(f"[Tableau] 找到 {len(views)} 个视图")

        results = []
        for v in views:
            view_info = {
                "id": v.get("id"),
                "name": v.get("name"),
                "url_name": v.get("viewUrlName"),
                "workbook_id": v.get("workbook", {}).get("id"),
                "content_url": v.get("contentUrl"),
            }

            if name_filter:
                if name_filter.lower() not in (view_info["name"] or "").lower():
                    continue

            results.append(view_info)

        return results

    finally:
        auth.signout()


def list_workbooks() -> list[dict[str, Any]]:
    """List available Tableau workbooks."""
    auth = get_auth()

    try:
        auth.signin()
    except Exception as e:
        print(f"[Error] 认证失败: {e}", file=sys.stderr)
        return []

    try:
        workbooks_url = f"{auth.api_base}/workbooks?pageSize=1000"
        print(f"[Tableau] 获取工作簿列表...")

        resp = requests.get(workbooks_url, headers=auth.get_headers(), timeout=60)
        resp.raise_for_status()

        workbooks = resp.json().get("workbooks", {}).get("workbook", [])
        print(f"[Tableau] 找到 {len(workbooks)} 个工作簿")

        return [
            {
                "id": wb.get("id"),
                "name": wb.get("name"),
                "project_name": wb.get("project", {}).get("name"),
                "content_url": wb.get("contentUrl"),
            }
            for wb in workbooks
        ]

    finally:
        auth.signout()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List Tableau views or workbooks")
    parser.add_argument("filter", nargs="?", help="按名称过滤视图")
    parser.add_argument("--workbooks", action="store_true", help="列出工作簿而不是视图")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.workbooks:
        workbooks = list_workbooks()
        if args.json:
            print(json.dumps(workbooks, ensure_ascii=False, indent=2))
            return 0
        for wb in workbooks:
            print(f"  [{wb['id'][:8]}...] {wb['name']} (项目: {wb['project_name']})")
        print(f"\n共 {len(workbooks)} 个工作簿")
        return 0

    views = list_views(args.filter)

    if args.json:
        print(json.dumps(views, ensure_ascii=False, indent=2))
        return 0

    if args.filter:
        print(f"\n过滤条件: '{args.filter}'")

    print(f"\n{'ID':<40} {'名称':<30} {'URL名称':<30}")
    print("-" * 100)

    for v in views:
        view_id = v["id"] or ""
        name = (v["name"] or "")[:30]
        url_name = (v["url_name"] or "")[:30]
        print(f"{view_id:<40} {name:<30} {url_name:<30}")

    print(f"\n共 {len(views)} 个视图")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
