#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def find_workspace(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "skills").is_dir() and (candidate / "metadata").is_dir():
            return candidate
        if (candidate / ".agents" / "skills").is_dir():
            return candidate
    raise SystemExit(f"Cannot find RealAnalyst workspace from {start}")


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def probe_project_python(workspace: Path, python_command: str) -> dict[str, Any]:
    command_path = workspace / "scripts" / "py" if python_command == "./scripts/py" else Path(python_command)
    code = """
import importlib.util, json, sys
mods = {name: importlib.util.find_spec(name) is not None for name in ["yaml", "duckdb", "pandas", "pymysql", "clickhouse_connect"]}
print(json.dumps({"python_executable": sys.executable, "dependencies": mods}))
""".strip()
    try:
        completed = subprocess.run(
            [str(command_path), "-c", code],
            cwd=workspace,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except Exception as exc:
        return {
            "python_executable": sys.executable,
            "dependencies": {name: module_available(name) for name in ("yaml", "duckdb", "pandas", "pymysql", "clickhouse_connect")},
            "probe_error": str(exc),
        }
    if completed.returncode != 0:
        return {
            "python_executable": sys.executable,
            "dependencies": {name: module_available(name) for name in ("yaml", "duckdb", "pandas", "pymysql", "clickhouse_connect")},
            "probe_error": (completed.stderr or completed.stdout).strip(),
        }
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {
            "python_executable": sys.executable,
            "dependencies": {name: module_available(name) for name in ("yaml", "duckdb", "pandas", "pymysql", "clickhouse_connect")},
            "probe_error": str(exc),
        }


def choose_recommended_skill(intent: str, *, has_metadata: bool, has_registry: bool) -> str:
    if intent == "metadata":
        return "RA:metadata"
    if intent == "export":
        return "RA:data-export" if has_registry else "RA:metadata"
    if intent == "refine":
        return "RA:metadata-refine"
    if intent == "verify":
        return "RA:report-verify"
    if intent == "analyze":
        return "RA:analysis-run" if has_metadata and has_registry else "RA:metadata"
    return "RA:metadata" if not has_metadata else "RA:analysis-run"


def build_summary(workspace: Path, intent: str) -> dict[str, Any]:
    source_skill_base = workspace / "skills"
    installed_skill_base = workspace / ".agents" / "skills"
    skill_base = source_skill_base if source_skill_base.is_dir() else installed_skill_base
    scripts_py = workspace / "scripts" / "py"
    lib_dir = workspace / "lib"
    log_utils = lib_dir / "log_utils.py"
    metadata_dir = workspace / "metadata"
    registry_path = workspace / "runtime" / "registry.db"
    metadata_py = skill_base / "metadata" / "scripts" / "metadata.py"
    data_export_dir = skill_base / "data-export" / "scripts"

    has_metadata = (metadata_dir / "datasets").is_dir() and any((metadata_dir / "datasets").glob("*.yaml"))
    has_registry = registry_path.exists()
    recommended_skill = choose_recommended_skill(intent, has_metadata=has_metadata, has_registry=has_registry)
    python_command = "./scripts/py" if scripts_py.exists() and scripts_py.stat().st_mode & 0o111 else sys.executable
    python_probe = probe_project_python(workspace, python_command)
    dependencies = {
        name: bool((python_probe.get("dependencies") or {}).get(name))
        for name in ("yaml", "duckdb", "pandas", "pymysql", "clickhouse_connect")
    }

    issues: list[str] = []
    remediation: list[dict[str, str]] = []
    if not scripts_py.exists():
        issues.append("scripts/py missing; run project setup or use the reported python_executable for read-only checks only.")
        remediation.append(
            {
                "code": "missing_scripts_py",
                "command": "python3 scripts/install_codex_plugin.py --project <target-project>",
                "note": "Refresh the project-local RealAnalyst runtime support before formal analysis.",
            }
        )
    elif python_probe.get("probe_error"):
        issues.append(f"scripts/py probe failed: {python_probe.get('probe_error')}")
        remediation.append(
            {
                "code": "scripts_py_probe_failed",
                "command": "./scripts/setup_venv.sh",
                "note": "Repair the project Python environment before formal analysis; do not fall back to ad hoc Python discovery.",
            }
        )
    if not log_utils.exists():
        issues.append("lib/log_utils.py missing; project-local scripts can run with a degraded logger, but install support files before formal analysis.")
        remediation.append(
            {
                "code": "missing_shared_lib",
                "command": "python3 scripts/install_codex_plugin.py --project <target-project> --force",
                "note": "Refresh project-local RealAnalyst support files, including shared lib helpers used by profiling and verification.",
            }
        )
    if not metadata_py.exists():
        issues.append("metadata.py missing from resolved skill base; reinstall or refresh RealAnalyst skills.")
        remediation.append(
            {
                "code": "missing_metadata_skill",
                "command": "python3 scripts/install_codex_plugin.py --project <target-project> --force",
                "note": "Refresh project-local skills; do not create business metadata during install.",
            }
        )
    if recommended_skill in {"RA:analysis-run", "RA:data-export"} and not has_registry:
        issues.append("runtime/registry.db missing; run RA:metadata validate/index/sync-registry before export or analysis.")
    if recommended_skill in {"RA:data-export", "RA:analysis-run"} and not dependencies["duckdb"]:
        issues.append("duckdb Python package missing for DuckDB-backed exports; run scripts/setup_venv.sh in this project.")
        remediation.append(
            {
                "code": "missing_duckdb_python",
                "command": "./scripts/setup_venv.sh",
                "note": "Install project Python dependencies so ./scripts/py can run DuckDB-backed export wrappers.",
            }
        )
    if recommended_skill in {"RA:data-export", "RA:analysis-run"} and not dependencies.get("pymysql"):
        issues.append("pymysql Python package missing for MySQL-backed exports; run scripts/setup_venv.sh in this project.")
        remediation.append(
            {
                "code": "missing_pymysql_python",
                "command": "./scripts/setup_venv.sh",
                "note": "Install project Python dependencies so ./scripts/py can run MySQL-backed export wrappers.",
            }
        )
    if recommended_skill in {"RA:data-export", "RA:analysis-run"} and not dependencies.get("clickhouse_connect"):
        issues.append("clickhouse-connect Python package missing for ClickHouse-backed exports; run scripts/setup_venv.sh in this project.")
        remediation.append(
            {
                "code": "missing_clickhouse_python",
                "command": "./scripts/setup_venv.sh",
                "note": "Install project Python dependencies so ./scripts/py can run ClickHouse-backed export wrappers.",
            }
        )

    return {
        "success": True,
        "workspace": str(workspace),
        "intent": intent,
        "environment": {
            "python_command": python_command,
            "python_executable": python_probe["python_executable"],
            "doctor_python_executable": sys.executable,
            "python_probe_error": python_probe.get("probe_error", ""),
            "skill_base_dir": str(skill_base),
            "source_skill_base_exists": source_skill_base.is_dir(),
            "installed_skill_base_exists": installed_skill_base.is_dir(),
            "scripts_py": str(scripts_py),
            "scripts_py_exists": scripts_py.exists(),
            "metadata_py": str(metadata_py),
            "metadata_py_exists": metadata_py.exists(),
            "lib_dir": str(lib_dir),
            "lib_dir_exists": lib_dir.is_dir(),
            "log_utils_py": str(log_utils),
            "log_utils_py_exists": log_utils.exists(),
            "registry_path": str(registry_path),
            "registry_exists": has_registry,
            "duckdb_path": str(workspace / "duckdb"),
            "duckdb_path_exists": (workspace / "duckdb").exists(),
            "dependencies": dependencies,
        },
        "readiness": {
            "metadata_yaml": has_metadata,
            "runtime_registry": has_registry,
            "data_export_scripts": data_export_dir.is_dir(),
            "metadata_write_allowed_only_via": "RA:metadata -> validate -> index -> sync-registry",
            "registry_write_allowed_only_via": "skills/metadata/scripts/metadata.py sync-registry",
        },
        "recommended_next_skill": recommended_skill,
        "issues": issues,
        "remediation": remediation,
        "guardrails": [
            "Do not discover ad hoc Python or DuckDB fallbacks during formal work.",
            "Do not write runtime/registry.db directly with sqlite3.",
            "Do not edit metadata/datasets/*.yaml for CSV header or display-name-only requests.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a read-only RealAnalyst project environment summary.")
    parser.add_argument("--workspace", default=None, help="Workspace root. Defaults to discovered RealAnalyst root.")
    parser.add_argument(
        "--intent",
        default="start",
        choices=("start", "analyze", "metadata", "export", "refine", "verify"),
        help="User intent used only to recommend the next skill.",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else find_workspace(Path(__file__).resolve())
    print(json.dumps(build_summary(workspace, args.intent), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
