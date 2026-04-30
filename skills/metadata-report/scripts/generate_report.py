#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import bootstrap_workspace_path
import duckdb_report
import tableau_report
from runtime.tableau import sqlite_store


WORKSPACE_DIR = bootstrap_workspace_path()


def _connector_from_dataset_id(dataset_id: str | None) -> str | None:
    if not dataset_id:
        return None
    prefix = dataset_id.split(".", 1)[0].lower()
    if prefix in {"duckdb", "tableau"}:
        return prefix
    return None


def _default_report_dir(workspace: Path, connector: str) -> Path:
    return workspace / "metadata" / "sync" / connector / "reports"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate RealAnalyst metadata Markdown reports")
    parser.add_argument("--workspace", help="Workspace root. Defaults to discovered RealAnalyst root.")
    parser.add_argument("--connector", choices=["duckdb", "tableau"], help="Connector report type")
    parser.add_argument("--dataset-id", help="Metadata dataset id, e.g. duckdb.ho.orders or tableau.route.-ai")
    parser.add_argument("--all", action="store_true", help="Generate reports for all active entries of the connector")
    parser.add_argument("--all-yaml", action="store_true", help="Generate reports for all YAML datasets of the connector")
    parser.add_argument("--report-dir", help="Output directory for Markdown reports")
    parser.add_argument("--with-samples", action="store_true", help="Indicate Tableau sync included sample values")
    parser.add_argument("--sync-mode", choices=["live", "dry-run", "metadata-yaml"], default="metadata-yaml")
    parser.add_argument("--register-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--registry-step-status", choices=["success", "failed", "skipped", "not_written"], default="success")
    parser.add_argument("--validate-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--fields-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--filters-step-status", choices=["success", "failed", "skipped"], default="success")
    parser.add_argument("--export-summary", help="Optional Tableau export_summary.json path")
    parser.add_argument("--manifest", help="Optional Tableau export manifest JSON path")
    return parser


def _generate_duckdb(args: argparse.Namespace, workspace: Path, report_dir: Path) -> None:
    duckdb_report.WORKSPACE_DIR = workspace
    duckdb_report.AGENTS_DIR = workspace / ".agents"
    sqlite_store._DB_PATH = workspace / "runtime" / "registry.db"
    generated_at = duckdb_report.datetime.now().astimezone()
    step_results = {
        "register": args.register_step_status,
        "registry": "not_written" if (args.dataset_id or args.all_yaml) else args.registry_step_status,
        "validate": args.validate_step_status,
    }

    if args.dataset_id or args.all_yaml:
        datasets = duckdb_report._load_yaml_datasets(workspace, dataset_id=args.dataset_id, all_yaml=args.all_yaml)
        validation_errors = duckdb_report._validate_yaml_datasets(workspace, datasets)
        if validation_errors:
            print("[Error] metadata validate failed:")
            for error in validation_errors:
                print(f"- {error}")
            raise SystemExit(1)
        step_results["validate"] = "success"
        for dataset in datasets:
            report_path = duckdb_report.write_yaml_report(
                workspace=workspace,
                dataset=dataset,
                report_dir=report_dir,
                generated_at=generated_at,
                step_results=step_results,
            )
            print(f"[OK] report -> {report_path}")
        return

    targets = duckdb_report._load_targets(key=None, all_entries=args.all)
    if not targets:
        print("[WARN] No DuckDB entries matched")
        return
    for entry in targets:
        key = str(entry.get("key") or "")
        dataset = duckdb_report._load_yaml_dataset_if_exists(workspace, str(entry.get("source_id") or key))
        if dataset is not None:
            report_path = duckdb_report.write_yaml_report(
                workspace=workspace,
                dataset=dataset,
                report_dir=report_dir,
                generated_at=generated_at,
                step_results=step_results,
            )
        else:
            spec = duckdb_report.load_spec_by_entry_key(key) or {}
            report_path = duckdb_report.write_report(
                entry=entry,
                spec=spec,
                report_dir=report_dir,
                generated_at=generated_at,
                sync_mode=args.sync_mode,
                step_results=step_results,
            )
        print(f"[OK] report -> {report_path}")


def _generate_tableau(args: argparse.Namespace, workspace: Path, report_dir: Path) -> None:
    tableau_report.WORKSPACE_DIR = workspace
    sqlite_store._DB_PATH = workspace / "runtime" / "registry.db"
    generated_at = tableau_report.datetime.now()
    step_results = {
        "fields": args.fields_step_status,
        "filters": args.filters_step_status,
        "registry": args.registry_step_status,
    }
    if args.dataset_id:
        targets = [
            entry
            for entry in tableau_report.list_entries(active_only=False)
            if isinstance(entry, dict)
            and (entry.get("source_id") == args.dataset_id or entry.get("key") == args.dataset_id)
        ]
    else:
        targets = tableau_report._load_targets(key=None, all_entries=args.all)
    if not targets:
        print("[WARN] No Tableau entries matched")
        return

    export_summary = tableau_report._parse_export_payload(args.export_summary)
    manifest = tableau_report._parse_export_payload(args.manifest)
    for entry in targets:
        key = str(entry.get("key") or "")
        spec = tableau_report.load_spec_by_entry_key(key) or {}
        context = tableau_report.build_source_context(entry)
        report_path = tableau_report.write_report(
            entry=entry,
            spec=spec,
            context=context,
            report_dir=report_dir,
            generated_at=generated_at,
            with_samples=args.with_samples,
            sync_mode=args.sync_mode if args.sync_mode != "metadata-yaml" else "live",
            step_results=step_results,
            export_summary=export_summary,
            manifest=manifest,
        )
        print(f"[OK] report -> {report_path}")


def main() -> None:
    args = build_parser().parse_args()
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else WORKSPACE_DIR
    connector = args.connector or _connector_from_dataset_id(args.dataset_id)
    if not connector:
        print("[Error] Specify --connector or use a dataset id starting with duckdb. / tableau.")
        raise SystemExit(2)
    if not args.dataset_id and not args.all and not args.all_yaml:
        print("[Error] Specify --dataset-id, --all, or --all-yaml")
        raise SystemExit(2)
    if args.all_yaml and connector == "tableau":
        print("[Error] --all-yaml is only supported for DuckDB reports")
        raise SystemExit(2)

    report_dir = Path(args.report_dir).expanduser().resolve() if args.report_dir else _default_report_dir(workspace, connector)
    if connector == "duckdb":
        _generate_duckdb(args, workspace, report_dir)
    else:
        _generate_tableau(args, workspace, report_dir)


if __name__ == "__main__":
    main()
