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
        self.assertIn(
            {
                "path": "skills/data-export/scripts/duckdb/export_duckdb_source.py",
                "mentioned_in_skill_or_readme": True,
            },
            skills["data-export"]["scripts"],
        )
        self.assertIn("skills/report/references/output-contract.md", skills["report"]["references"])

    def test_audit_inventory_covers_handoff_matrix(self) -> None:
        audit = _load_audit_module()
        payload = audit.run_audit()
        matrix = payload["inventory"]["handoff_matrix"]

        self.assertEqual(len(matrix), len(audit.EXPECTED_PIPELINE_SKILLS) - 1)
        self.assertEqual(
            [(edge["from"], edge["to"]) for edge in matrix],
            list(zip(audit.EXPECTED_PIPELINE_SKILLS, audit.EXPECTED_PIPELINE_SKILLS[1:])),
        )
        self.assertTrue(all(edge["complete"] for edge in matrix))

    def test_data_export_to_data_profile_handoff_has_required_contract_tokens(self) -> None:
        audit = _load_audit_module()
        matrix = audit.build_handoff_matrix()
        edge = next(item for item in matrix if item["from"] == "data-export" and item["to"] == "data-profile")

        checks = edge["checks"]
        self.assertTrue(checks["producer_outputs"]["found"])
        self.assertTrue(checks["consumer_inputs"]["found"])
        self.assertTrue(checks["trigger_or_next_step"]["found"])
        self.assertTrue(checks["state_update"]["found"])
        self.assertIn(["export_summary"], [item["tokens"] for item in checks["producer_outputs"]["token_groups"]])
        self.assertIn(["duckdb_export_summary.json"], [item["tokens"] for item in checks["consumer_inputs"]["token_groups"]])
        self.assertIn(["RA:data-profile"], [item["tokens"] for item in checks["trigger_or_next_step"]["token_groups"]])
        self.assertIn(["job_manifest 更新"], [item["tokens"] for item in checks["state_update"]["token_groups"]])

    def test_report_to_report_verify_handoff_has_required_contract_tokens(self) -> None:
        audit = _load_audit_module()
        matrix = audit.build_handoff_matrix()
        edge = next(item for item in matrix if item["from"] == "report" and item["to"] == "report-verify")

        checks = edge["checks"]
        self.assertTrue(checks["producer_outputs"]["found"])
        self.assertTrue(checks["consumer_inputs"]["found"])
        self.assertTrue(checks["trigger_or_next_step"]["found"])
        self.assertTrue(checks["state_update"]["found"])
        self.assertIn(["输出文件清单"], [item["tokens"] for item in checks["producer_outputs"]["token_groups"]])
        self.assertIn(["report_md"], [item["tokens"] for item in checks["consumer_inputs"]["token_groups"]])
        self.assertIn(["RA:report-verify"], [item["tokens"] for item in checks["trigger_or_next_step"]["token_groups"]])
        self.assertIn(["verification.json"], [item["tokens"] for item in checks["state_update"]["token_groups"]])

    def test_audit_inventory_covers_metadata_relationships(self) -> None:
        audit = _load_audit_module()
        payload = audit.run_audit()
        metadata_files = payload["inventory"]["metadata_files"]

        self.assertIn("metadata/datasets/demo.retail.orders.yaml", metadata_files["datasets"])
        self.assertIn("metadata/mappings/demo.retail.orders.mapping.yaml", metadata_files["mappings"])
        self.assertIn("metadata/dictionaries/demo.retail.dictionary.yaml", metadata_files["dictionaries"])
        self.assertIn("metadata/models/demo_retail.yaml", metadata_files["models"])
        self.assertIn("metadata/sources/demo.md", metadata_files["sources"])
        self.assertGreaterEqual(metadata_files["counts"]["sync_reports"], 1)
        self.assertGreaterEqual(metadata_files["counts"]["generated_index"], 1)

    def test_audit_inventory_covers_code_files_and_internal_script_candidates(self) -> None:
        audit = _load_audit_module()
        payload = audit.run_audit()
        code_files = payload["inventory"]["code_files"]

        self.assertGreaterEqual(code_files["python_file_count"], 50)
        self.assertGreaterEqual(code_files["test_file_count"], 10)
        self.assertIn("runtime/job_manifest.py", code_files["runtime_files"])
        self.assertIn("scripts/audit_project_contracts.py", code_files["project_scripts"])
        self.assertIn("tests/test_project_contract_audit.py", code_files["test_files"])
        self.assertIn("skills/metadata/adapters/tableau/scripts/test_views.py", code_files["manual_smoke_scripts_outside_tests"])
        self.assertIn("skills/data-export/scripts/sql/common_sql_export.py", code_files["potentially_internal_or_unreferenced_skill_scripts"])
        self.assertIn("test.sh", code_files["shell_entrypoints"])

    def test_project_audit_report_lists_internal_script_candidates(self) -> None:
        audit = _load_audit_module()
        payload = audit.run_audit()
        candidates = payload["inventory"]["code_files"]["potentially_internal_or_unreferenced_skill_scripts"]
        report = (REPO / "tests" / "reports" / "2026-06-18-project-audit-gates.md").read_text(encoding="utf-8")

        self.assertGreaterEqual(len(candidates), 20)
        for script_path in candidates:
            self.assertIn(script_path, report)

    def test_audit_inventory_covers_code_surface_test_document_matrix(self) -> None:
        audit = _load_audit_module()
        payload = audit.run_audit()
        matrix = payload["inventory"]["code_surface_matrix"]
        surfaces = {item["id"]: item for item in matrix}

        expected_surfaces = {
            "one_click_test_entry",
            "project_contract_audit",
            "job_manifest_runtime",
            "analysis_run_job_lifecycle",
            "analysis_plan_contract",
            "artifact_registration",
            "report_manifest_delivery",
            "report_verify_user_surface",
            "legacy_migration_archive",
            "metadata_layering_and_references",
        }
        self.assertEqual(set(surfaces), expected_surfaces)
        for surface in matrix:
            for path in surface["implementation_paths"] + surface["test_paths"] + surface["report_paths"]:
                self.assertTrue((REPO / path).exists(), f"{surface['id']} missing {path}")

        self.assertIn("runtime/job_manifest.py", surfaces["job_manifest_runtime"]["implementation_paths"])
        self.assertIn("tests/test_job_manifest.py", surfaces["job_manifest_runtime"]["test_paths"])
        self.assertIn(
            "tests/reports/2026-06-18-code-surface-coverage.md",
            surfaces["job_manifest_runtime"]["report_paths"],
        )

    def test_audit_inventory_classifies_every_python_file_with_test_strategy(self) -> None:
        audit = _load_audit_module()
        payload = audit.run_audit()
        code_files = payload["inventory"]["code_files"]
        coverage = code_files["code_file_coverage"]

        self.assertEqual(len(coverage), code_files["python_file_count"])
        self.assertFalse([item for item in coverage if item["category"] == "unclassified"])
        for item in coverage:
            self.assertTrue(item["test_paths"], item["path"])
            self.assertTrue(item["report_paths"], item["path"])
            for path in item["test_paths"] + item["report_paths"]:
                self.assertTrue((REPO / path).exists(), f"{item['path']} references missing {path}")

        categories = {item["category"] for item in coverage}
        self.assertIn("code_surface", categories)
        self.assertIn("documented_skill_script", categories)
        self.assertIn("internal_or_unreferenced_skill_script", categories)
        self.assertIn("metadata_adapter_script", categories)
        self.assertIn("platform_integration_support", categories)
        self.assertIn("trellis_runtime_support", categories)

    def test_metadata_reference_audit_has_no_missing_source_evidence(self) -> None:
        audit = _load_audit_module()
        findings: list[dict] = []
        audit.audit_metadata(findings)
        source_evidence_errors = [
            item
            for item in findings
            if item["check"] in {"metadata_reference", "metadata_source_evidence"}
        ]
        self.assertEqual(source_evidence_errors, [])

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
