#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from _bootstrap import ensure_workspace_on_path


COMMANDS = (
    "init",
    "init-source",
    "validate",
    "index",
    "search",
    "context",
    "inventory",
    "export-osi",
    "list-commands",
)
SCRIPT_DIR = Path(__file__).resolve().parent


def run_python_script(workspace: Path, script: Path, args: list[str]) -> int:
    completed = subprocess.run([sys.executable, str(script), *args], cwd=workspace, check=False)
    return completed.returncode


def metadata_script(name: str) -> Path:
    return SCRIPT_DIR / name


def adapter_plan(workspace: Path, *, backend: str, source_id: str, dry_run: bool) -> dict[str, Any]:
    if backend == "tableau":
        scripts = [
            "skills/metadata/adapters/tableau/scripts/discover.py",
            "skills/metadata/adapters/tableau/scripts/sync_fields.py",
            "skills/metadata/adapters/tableau/scripts/sync_filters.py",
            "skills/metadata/adapters/tableau/scripts/generate_sync_report.py",
        ]
    else:
        scripts = [
            "skills/metadata/adapters/duckdb/scripts/discover_catalog.py",
            "skills/metadata/adapters/duckdb/scripts/inspect_source.py",
            "skills/metadata/adapters/duckdb/scripts/generate_sync_report.py",
        ]
    return {
        "success": True,
        "mode": "adapter-plan",
        "backend": backend,
        "source_id": source_id,
        "dry_run": dry_run,
        "workspace": str(workspace),
        "adapter_scripts": scripts,
        "next_step": "Use adapter output as source material, then maintain metadata/datasets/*.yaml.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified RealAnalyst metadata command.")
    parser.add_argument("--workspace", default=None, help="Workspace root. Defaults to discovered RealAnalyst root.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-commands", help="Print available metadata commands.")

    init = subparsers.add_parser("init", help="Initialize metadata workspace files.")
    init.add_argument("--force", action="store_true", help="Overwrite existing scaffold files.")
    init.add_argument("--with-demo", action="store_true", help="Also copy demo metadata files.")

    subparsers.add_parser("validate", help="Validate metadata YAML.")
    subparsers.add_parser("index", help="Build metadata JSONL indexes.")
    subparsers.add_parser("inventory", help="Build metadata system inventory.")

    init_source = subparsers.add_parser("init-source", help="Build a connector adapter handoff plan.")
    init_source.add_argument("--backend", required=True, choices=("tableau", "duckdb"))
    init_source.add_argument("--source-id", required=True)
    init_source.add_argument("--dry-run", action="store_true")

    search = subparsers.add_parser("search", help="Search metadata indexes.")
    search.add_argument("--type", default="all", choices=("all", "dataset", "field", "metric", "mapping", "term", "glossary"))
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=10)

    context = subparsers.add_parser("context", help="Build an analysis context pack.")
    context_ref = context.add_mutually_exclusive_group(required=True)
    context_ref.add_argument("--dataset-id", dest="dataset_ref", help="Metadata dataset id, for example demo.retail.orders")
    context_ref.add_argument("--source-id", dest="dataset_ref", help="Backward-compatible alias for dataset/source references")
    context.add_argument("--metric", action="append", default=[])
    context.add_argument("--field", action="append", default=[])

    export_osi = subparsers.add_parser("export-osi", help="Export metadata YAML into an OSI semantic model YAML.")
    export_osi.add_argument("--model-name", required=True)
    export_osi.add_argument("--output", default=None)

    return parser


def workspace_args(workspace: Path) -> list[str]:
    return ["--workspace", str(workspace)]


def main(argv: list[str] | None = None) -> int:
    default_workspace = ensure_workspace_on_path()
    args = build_parser().parse_args(argv)
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else default_workspace

    if args.command == "list-commands":
        print(json.dumps({"success": True, "commands": list(COMMANDS)}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "init":
        forwarded = workspace_args(workspace)
        if args.force:
            forwarded.append("--force")
        if args.with_demo:
            forwarded.append("--with-demo")
        return run_python_script(workspace, metadata_script("init_metadata.py"), forwarded)

    if args.command == "validate":
        return run_python_script(workspace, metadata_script("validate_metadata.py"), workspace_args(workspace))

    if args.command == "index":
        return run_python_script(workspace, metadata_script("build_index.py"), workspace_args(workspace))

    if args.command == "inventory":
        return run_python_script(workspace, metadata_script("build_inventory.py"), workspace_args(workspace))

    if args.command == "search":
        record_type = "term" if args.type == "glossary" else args.type
        return run_python_script(
            workspace,
            metadata_script("search_metadata.py"),
            [*workspace_args(workspace), "--type", record_type, "--query", args.query, "--limit", str(args.limit)],
        )

    if args.command == "context":
        forwarded = [*workspace_args(workspace), "--dataset-id", args.dataset_ref]
        for metric in args.metric:
            forwarded.extend(["--metric", metric])
        for field in args.field:
            forwarded.extend(["--field", field])
        return run_python_script(
            workspace,
            metadata_script("build_context.py"),
            forwarded,
        )

    if args.command == "export-osi":
        forwarded = [*workspace_args(workspace), "--model-name", args.model_name]
        if args.output:
            forwarded.extend(["--output", args.output])
        return run_python_script(workspace, metadata_script("export_osi.py"), forwarded)

    if args.command == "init-source":
        print(json.dumps(adapter_plan(workspace, backend=args.backend, source_id=args.source_id, dry_run=args.dry_run), ensure_ascii=False, indent=2))
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
