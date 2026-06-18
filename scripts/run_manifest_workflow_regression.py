#!/usr/bin/env python3
"""Run focused manifest/workflow regression gates."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

FOCUSED_TESTS = [
    "tests/test_job_manifest.py",
    "tests/test_analysis_run_manifest_integration.py",
    "tests/test_report_manifest_deliverables.py",
    "tests/test_report_verify_user_surface.py",
    "tests/test_export_profile_manifest_registration.py",
    "tests/test_analysis_reference_frameworks.py",
    "tests/test_analysis_plan_contract.py",
    "tests/test_ci_workflows.py",
    "tests/test_legacy_job_manifest_migration.py",
    "tests/test_finalize_job_archive.py",
]

SCHEMAS = [
    "schemas/job_manifest.schema.json",
    "schemas/analysis_plan.schema.json",
    "schemas/analysis_plan_decision.schema.json",
    "schemas/manifest.schema.json",
    "schemas/verification.schema.json",
]


def run(command: list[str], *, quiet: bool = False) -> int:
    proc = subprocess.run(command, cwd=REPO, stdout=subprocess.DEVNULL if quiet else None)
    return proc.returncode


def main() -> int:
    commands = [
        [sys.executable, "-m", "compileall", "-q", "skills", "runtime", "scripts", ".trellis/scripts"],
        [sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS],
    ]
    commands.extend([[sys.executable, "-m", "json.tool", schema] for schema in SCHEMAS])

    for command in commands:
        code = run(command, quiet=command[2:3] == ["json.tool"])
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
