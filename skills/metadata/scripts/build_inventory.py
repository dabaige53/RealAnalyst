#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import bootstrap_workspace_path


WORKSPACE_DIR = bootstrap_workspace_path()

from skills.metadata.lib.metadata_inventory import build_inventory, write_inventory_json


def render_markdown(inventory: dict) -> str:
    lines = ["# Metadata System Inventory", "", "## 文件角色汇总", ""]
    for role, count in sorted(inventory["summary"].items()):
        lines.append(f"- `{role}`: {count}")
    lines.extend(["", "## 文件清单", ""])
    for item in inventory["files"]:
        lines.append(f"- `{item['path']}`：`{item['role']}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build current metadata system inventory.")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--markdown-output", default=None)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    json_output = (
        Path(args.json_output).expanduser().resolve()
        if args.json_output
        else workspace / "docs" / "metadata-system-inventory.json"
    )
    markdown_output = (
        Path(args.markdown_output).expanduser().resolve()
        if args.markdown_output
        else workspace / "docs" / "metadata-system-inventory.md"
    )

    inventory = build_inventory(workspace)
    write_inventory_json(json_output, inventory)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_markdown(inventory), encoding="utf-8")

    print(
        json.dumps(
            {
                "success": True,
                "workspace": str(workspace),
                "json_output": str(json_output),
                "markdown_output": str(markdown_output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
