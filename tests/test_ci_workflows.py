from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any

import yaml


REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"
REGRESSION_SCRIPT = REPO / "scripts" / "run_manifest_workflow_regression.py"
TEST_SH = REPO / "test.sh"


def _load_workflow(name: str) -> dict[str, Any]:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _workflow_on(workflow: dict[str, Any]) -> dict[str, Any]:
    # PyYAML keeps YAML 1.1 boolean handling, so GitHub's "on" key may load as True.
    return workflow.get("on") or workflow.get(True) or {}


def _run_commands(workflow: dict[str, Any], job_name: str) -> list[str]:
    steps = workflow["jobs"][job_name]["steps"]
    return [step["run"].strip() for step in steps if "run" in step]


def _load_regression_module():
    spec = importlib.util.spec_from_file_location("manifest_workflow_regression_test", REGRESSION_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load run_manifest_workflow_regression.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CIWorkflowTests(unittest.TestCase):
    def test_ci_uses_one_click_public_test_entrypoint(self) -> None:
        workflow = _load_workflow("ci.yml")

        self.assertIn("push", _workflow_on(workflow))
        self.assertIn("pull_request", _workflow_on(workflow))
        self.assertEqual(workflow["jobs"]["public-checks"]["runs-on"], "ubuntu-latest")

        steps = workflow["jobs"]["public-checks"]["steps"]
        setup_python = next(step for step in steps if step.get("uses") == "actions/setup-python@v5")
        self.assertEqual(setup_python["with"]["python-version"], "3.11")

        commands = "\n".join(_run_commands(workflow, "public-checks"))
        self.assertIn("python -m pip install -r requirements.txt", commands)
        self.assertIn("bash test.sh", commands)
        self.assertNotIn("python scripts/run_manifest_workflow_regression.py", commands)

    def test_test_sh_runs_public_unit_and_manifest_regression_gates(self) -> None:
        script = TEST_SH.read_text(encoding="utf-8")

        expected_order = [
            "-m json.tool .codex-plugin/plugin.json",
            "skills/metadata/scripts/metadata.py validate",
            "skills/metadata/scripts/metadata.py index",
            "scripts/audit_project_contracts.py",
            "-m unittest tests.test_ci_workflows",
            "-m unittest discover -s tests",
            "scripts/run_manifest_workflow_regression.py",
            "git diff --check",
        ]
        positions = []
        for token in expected_order:
            self.assertIn(token, script)
            positions.append(script.index(token))
        self.assertEqual(positions, sorted(positions))

    def test_test_sh_builds_metadata_index_before_audit(self) -> None:
        """metadata/index/ is gitignored; test.sh must regenerate it before the
        audit so fresh-clone / CI runs do not fail the generated_index>=1 gate."""
        script = TEST_SH.read_text(encoding="utf-8")

        validate_pos = script.index("skills/metadata/scripts/metadata.py validate")
        index_pos = script.index("skills/metadata/scripts/metadata.py index")
        audit_pos = script.index("scripts/audit_project_contracts.py")

        self.assertLess(validate_pos, index_pos, "index must run after validate")
        self.assertLess(index_pos, audit_pos, "index must run before the project audit")

    def test_issue_spam_workflow_has_minimal_permissions_and_tested_script(self) -> None:
        workflow = _load_workflow("issue-spam-moderation.yml")

        triggers = _workflow_on(workflow)
        self.assertEqual(triggers["issues"]["types"], ["opened", "edited"])
        self.assertEqual(triggers["issue_comment"]["types"], ["created", "edited"])
        self.assertEqual(workflow["permissions"], {"contents": "read", "issues": "write"})

        job = workflow["jobs"]["payment-address-filter"]
        self.assertEqual(job["runs-on"], "ubuntu-latest")
        commands = _run_commands(workflow, "payment-address-filter")
        self.assertEqual(commands, ["python scripts/moderate_issue_spam.py"])

        remove_step = next(step for step in job["steps"] if step.get("name") == "Remove Payment Address spam")
        self.assertEqual(remove_step["env"]["GITHUB_TOKEN"], "${{ secrets.GITHUB_TOKEN }}")

    def test_manifest_regression_gate_keeps_ci_contract_tests(self) -> None:
        module = _load_regression_module()

        self.assertIn("tests/test_ci_workflows.py", module.FOCUSED_TESTS)
        self.assertIn("tests/test_report_manifest_deliverables.py", module.FOCUSED_TESTS)
        self.assertIn("tests/test_report_verify_user_surface.py", module.FOCUSED_TESTS)
        self.assertIn("schemas/job_manifest.schema.json", module.SCHEMAS)


if __name__ == "__main__":
    unittest.main()
