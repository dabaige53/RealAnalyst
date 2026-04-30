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
    "catalog",
    "reconcile",
    "profile-review",
    "enrich-definitions",
    "sync-registry",
    "status",
    "inventory",
    "export-osi",
    "record-change",
    "change-report",
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
        ]
    else:
        scripts = [
            "skills/metadata/adapters/duckdb/scripts/discover_catalog.py",
            "skills/metadata/adapters/duckdb/scripts/inspect_source.py",
        ]
    return {
        "success": True,
        "mode": "adapter-plan",
        "backend": backend,
        "source_id": source_id,
        "dry_run": dry_run,
        "workspace": str(workspace),
        "adapter_scripts": scripts,
        "next_step": "Archive adapter output in metadata/sources/, maintain metadata/dictionaries/*.yaml, metadata/mappings/*.yaml, and metadata/datasets/*.yaml, then use RA:metadata-report to generate Markdown reports.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified RealAnalyst metadata command.")
    parser.add_argument("--workspace", default=None, help="Workspace root. Defaults to discovered RealAnalyst root.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-commands", help="Print available metadata commands.")

    init = subparsers.add_parser("init", help="Initialize metadata workspace files.")
    init.add_argument("--force", action="store_true", help="Overwrite existing scaffold files.")
    init.add_argument("--with-demo", action="store_true", help="Also copy demo metadata files.")

    validate = subparsers.add_parser("validate", help="Validate metadata YAML.")
    validate.add_argument("--completeness", action="store_true", help="Also check metric/mapping/profile completeness.")
    validate.add_argument("--strict", action="store_true", help="Alias for --completeness plus strict gates.")
    subparsers.add_parser("index", help="Build metadata JSONL indexes.")
    subparsers.add_parser("inventory", help="Build metadata system inventory.")
    subparsers.add_parser("change-report", help="Regenerate the metadata change audit report.")

    record_change = subparsers.add_parser("record-change", help="Append a metadata maintenance audit record and refresh the report.")
    record_change.add_argument("--summary", required=True)
    record_change.add_argument("--change-type", default="maintenance")
    record_change.add_argument("--path", action="append", default=[])
    record_change.add_argument("--before", action="append", default=[], help="Before-copy path for changed YAML. Repeat in the same order as --path.")
    record_change.add_argument("--dataset-id", action="append", default=[])
    record_change.add_argument("--refine-id", default="")
    record_change.add_argument("--evidence", action="append", default=[])
    record_change.add_argument("--details", default="")
    record_change.add_argument("--actor", default="llm")

    enrich = subparsers.add_parser("enrich-definitions", help="Enrich dataset business definitions from mappings and dictionaries.")
    enrich.add_argument("--dataset-id", action="append", required=True)

    sync_registry = subparsers.add_parser("sync-registry", help="Sync validated dataset YAML into runtime/registry.db.")
    sync_scope = sync_registry.add_mutually_exclusive_group(required=True)
    sync_scope.add_argument("--dataset-id")
    sync_scope.add_argument("--all", action="store_true")
    sync_registry.add_argument("--dry-run", action="store_true")

    status = subparsers.add_parser("status", help="Show metadata/index/runtime registry status.")
    status_scope = status.add_mutually_exclusive_group(required=True)
    status_scope.add_argument("--dataset-id")
    status_scope.add_argument("--all", action="store_true")

    init_source = subparsers.add_parser("init-source", help="Build a connector adapter handoff plan.")
    init_source.add_argument("--backend", required=True, choices=("tableau", "duckdb"))
    init_source.add_argument("--source-id", required=True)
    init_source.add_argument("--dry-run", action="store_true")

    search = subparsers.add_parser("search", help="Search metadata indexes.")
    search.add_argument("--type", default="all", choices=("all", "dataset", "field", "metric", "mapping", "term", "glossary"))
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=10)

    context = subparsers.add_parser("context", help="Build an analysis context pack.")
    context.add_argument("--dataset-id", action="append", required=True, help="Metadata dataset id (repeatable for multi-dataset context)")
    context.add_argument("--metric", action="append", default=[])
    context.add_argument("--field", action="append", default=[])

    catalog = subparsers.add_parser("catalog", help="Build a lightweight dataset catalog summary.")
    catalog.add_argument("--domain", default=None, help="Filter datasets by business domain.")
    catalog.add_argument("--group-by", dest="group_by", choices=["domain"], default=None, help="Group output by field.")

    reconcile = subparsers.add_parser("reconcile", help="Reconcile runtime registry lookup tables vs metadata YAML.")
    reconcile.add_argument("--runtime-db", default=None, help="Path to runtime SQLite DB. Defaults to runtime/registry.db.")

    profile_review = subparsers.add_parser("profile-review", help="Review metadata completeness against profile/refine evidence.")
    profile_review.add_argument("--dataset-id", required=True)
    profile_review.add_argument("--profile-json", default="")
    profile_review.add_argument("--refine-id", default="")
    profile_review.add_argument("--output-dir", default="metadata/audit/profile-review")

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
        forwarded = workspace_args(workspace)
        if args.completeness:
            forwarded.append("--completeness")
        if args.strict:
            forwarded.append("--strict")
        return run_python_script(workspace, metadata_script("validate_metadata.py"), forwarded)

    if args.command == "index":
        return run_python_script(workspace, metadata_script("build_index.py"), workspace_args(workspace))

    if args.command == "inventory":
        return run_python_script(workspace, metadata_script("build_inventory.py"), workspace_args(workspace))

    if args.command == "change-report":
        return run_python_script(workspace, metadata_script("metadata_audit.py"), [*workspace_args(workspace), "report"])

    if args.command == "record-change":
        forwarded = [
            *workspace_args(workspace),
            "record",
            "--summary",
            args.summary,
            "--change-type",
            args.change_type,
            "--actor",
            args.actor,
        ]
        if args.details:
            forwarded.extend(["--details", args.details])
        if args.refine_id:
            forwarded.extend(["--refine-id", args.refine_id])
        for path in args.path:
            forwarded.extend(["--path", path])
        for before in args.before:
            forwarded.extend(["--before", before])
        for dataset_id in args.dataset_id:
            forwarded.extend(["--dataset-id", dataset_id])
        for evidence in args.evidence:
            forwarded.extend(["--evidence", evidence])
        return run_python_script(workspace, metadata_script("metadata_audit.py"), forwarded)

    if args.command == "enrich-definitions":
        forwarded = workspace_args(workspace)
        for dataset_id in args.dataset_id:
            forwarded.extend(["--dataset-id", dataset_id])
        return run_python_script(workspace, metadata_script("enrich_definitions.py"), forwarded)

    if args.command == "sync-registry":
        forwarded = workspace_args(workspace)
        if args.all:
            forwarded.append("--all")
        else:
            forwarded.extend(["--dataset-id", args.dataset_id])
        if args.dry_run:
            forwarded.append("--dry-run")
        return run_python_script(workspace, metadata_script("sync_registry.py"), forwarded)

    if args.command == "status":
        forwarded = workspace_args(workspace)
        if args.all:
            forwarded.append("--all")
        else:
            forwarded.extend(["--dataset-id", args.dataset_id])
        return run_python_script(workspace, metadata_script("status_registry.py"), forwarded)

    if args.command == "search":
        record_type = "term" if args.type == "glossary" else args.type
        return run_python_script(
            workspace,
            metadata_script("search_metadata.py"),
            [*workspace_args(workspace), "--type", record_type, "--query", args.query, "--limit", str(args.limit)],
        )

    if args.command == "context":
        forwarded = list(workspace_args(workspace))
        for did in args.dataset_id:
            forwarded.extend(["--dataset-id", did])
        for metric in args.metric:
            forwarded.extend(["--metric", metric])
        for field in args.field:
            forwarded.extend(["--field", field])
        return run_python_script(
            workspace,
            metadata_script("build_context.py"),
            forwarded,
        )

    if args.command == "catalog":
        forwarded = list(workspace_args(workspace))
        if args.domain:
            forwarded.extend(["--domain", args.domain])
        if args.group_by:
            forwarded.extend(["--group-by", args.group_by])
        return run_python_script(
            workspace,
            metadata_script("build_catalog.py"),
            forwarded,
        )

    if args.command == "reconcile":
        forwarded = list(workspace_args(workspace))
        if args.runtime_db:
            forwarded.extend(["--runtime-db", args.runtime_db])
        return run_python_script(
            workspace,
            metadata_script("reconcile_metadata.py"),
            forwarded,
        )

    if args.command == "profile-review":
        forwarded = [*workspace_args(workspace), "--dataset-id", args.dataset_id]
        if args.profile_json:
            forwarded.extend(["--profile-json", args.profile_json])
        if args.refine_id:
            forwarded.extend(["--refine-id", args.refine_id])
        if args.output_dir:
            forwarded.extend(["--output-dir", args.output_dir])
        return run_python_script(workspace, metadata_script("profile_review.py"), forwarded)

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
