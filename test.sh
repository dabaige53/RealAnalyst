#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python3}"

run() {
  printf '\n==> %s\n' "$*"
  "$@"
}

run "$PYTHON_BIN" -m json.tool .codex-plugin/plugin.json
run "$PYTHON_BIN" skills/metadata/scripts/metadata.py validate
run "$PYTHON_BIN" scripts/audit_project_contracts.py
run "$PYTHON_BIN" -m unittest tests.test_ci_workflows
run "$PYTHON_BIN" -m unittest discover -s tests
run "$PYTHON_BIN" scripts/run_manifest_workflow_regression.py
run git diff --check
