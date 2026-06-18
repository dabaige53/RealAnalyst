from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = REPO / "scripts" / "audit_project_contracts.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("project_contract_audit", AUDIT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load audit_project_contracts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProjectContractAuditTests(unittest.TestCase):
    def test_audit_script_outputs_json_and_no_errors(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            cwd=REPO,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["summary"]["findings"]["error"], 0)
        self.assertEqual(payload["summary"]["findings"]["warning"], 0)
        self.assertGreaterEqual(payload["summary"]["skills_checked"], 10)

    def test_audit_inventory_covers_delivery_chain_contracts(self) -> None:
        audit = _load_audit_module()
        payload = audit.run_audit()
        inventory = payload["inventory"]
        skills = {item["id"]: item for item in inventory["skills"]}
        self.assertEqual(inventory["delivery_chain"], audit.EXPECTED_PIPELINE_SKILLS)
        self.assertIn("data-export", skills)
        self.assertTrue(skills["data-export"]["has_input_output_section"])
        self.assertTrue(skills["data-export"]["has_next_step_row"])
        self.assertTrue(all(skills["data-export"]["delivery_tokens"].values()))

    def test_test_sh_runs_project_contract_audit(self) -> None:
        script = (REPO / "test.sh").read_text(encoding="utf-8")
        self.assertIn("scripts/audit_project_contracts.py", script)

    def test_ra_skill_prefix_matches_skill_directory(self) -> None:
        audit = _load_audit_module()
        findings: list[dict] = []
        audit.audit_skills(findings)
        prefix_warnings = [
            item
            for item in findings
            if item["check"] == "skill_frontmatter" and "RA:" in item["message"]
        ]
        self.assertEqual(prefix_warnings, [])

    def test_pytest_collection_audit_ignores_virtualenv_and_tests_directory(self) -> None:
        audit = _load_audit_module()
        findings: list[dict] = []
        audit.audit_python_collection(findings)
        paths = {str(item.get("path") or "") for item in findings}
        self.assertFalse(any(path.startswith(".venv/") for path in paths))
        self.assertFalse(any(path.startswith("tests/") for path in paths))


if __name__ == "__main__":
    unittest.main()
