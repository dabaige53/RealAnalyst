from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[1]
METADATA = REPO / "skills" / "metadata" / "scripts" / "metadata.py"
REFINE_BUILD = REPO / "skills" / "metadata-refine" / "scripts" / "build_reference_pack.py"
DUCKDB_EXPORTER = REPO / "skills" / "data-export" / "scripts" / "duckdb" / "export_duckdb_source.py"
DUCKDB_REPORTER = REPO / "skills" / "metadata" / "adapters" / "duckdb" / "scripts" / "generate_sync_report.py"


def definition(text: str = "已确认业务定义") -> dict:
    return {
        "text": text,
        "source_type": "user_confirmed",
        "confidence": 0.9,
        "source_evidence": [{"type": "test", "source": "tests", "quote": "fixture"}],
        "needs_review": False,
    }


def write_dataset(workspace: Path, *, metric_field_count: int, metric_count: int, include_mapping_gap: bool = False) -> None:
    fields = []
    metrics = []
    for index in range(metric_field_count):
        name = f"metric_field_{index}"
        fields.append(
            {
                "name": name,
                "display_name": name,
                "role": "metric_source",
                "type": "number",
                "description": f"{name} description",
                "business_definition": definition(f"{name} business definition"),
            }
        )
        if index < metric_count:
            metrics.append(
                {
                    "name": name,
                    "display_name": name,
                    "expression": name,
                    "description": f"{name} metric",
                    "business_definition": definition(f"{name} metric definition"),
                }
            )
    fields.append(
        {
            "name": "year",
            "display_name": "year",
            "role": "dimension",
            "type": "number",
            "description": "year dimension",
            "business_definition": definition("year dimension definition"),
        }
    )
    dataset = {
        "version": 1,
        "id": "test.dataset",
        "display_name": "Test Dataset",
        "source": {"connector": "duckdb", "object": "test.dataset"},
        "business": {"grain": [], "primary_key": [], "time_fields": [], "suitable_for": [], "not_suitable_for": [], "sample_questions": []},
        "maintenance": {"owner": "test", "pending_questions": []},
        "fields": fields,
        "metrics": metrics,
    }
    mapping_metric = "missing_metric" if include_mapping_gap else "metric_field_0"
    mapping = {
        "version": 1,
        "id": "test.dataset.mapping",
        "kind": "mapping",
        "source_id": "test.dataset",
        "display_name": "Test Mapping",
        "source_evidence": [{"type": "test", "source": "tests", "quote": "fixture"}],
        "mappings": [{"type": "metric", "view_field": mapping_metric, "standard_id": mapping_metric}],
    }
    (workspace / "metadata" / "datasets").mkdir(parents=True)
    (workspace / "metadata" / "mappings").mkdir(parents=True)
    (workspace / "metadata" / "dictionaries").mkdir(parents=True)
    (workspace / "metadata" / "datasets" / "test.dataset.yaml").write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")
    (workspace / "metadata" / "mappings" / "test.dataset.mapping.yaml").write_text(yaml.safe_dump(mapping, allow_unicode=True), encoding="utf-8")


class MetadataProductFixTests(unittest.TestCase):
    def run_cmd(self, args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, cwd=cwd or REPO, text=True, capture_output=True)

    def test_profile_review_reports_unregistered_metric_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=54, metric_count=8)
            proc = self.run_cmd(
                [
                    sys.executable,
                    str(METADATA),
                    "--workspace",
                    str(workspace),
                    "profile-review",
                    "--dataset-id",
                    "test.dataset",
                    "--output-dir",
                    str(workspace / "reports"),
                ]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["summary"]["should_add_metrics"], 46)
            self.assertTrue((workspace / payload["outputs"]["markdown"]).exists())

    def test_validate_completeness_blocks_mapping_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1, include_mapping_gap=True)
            proc = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate", "--completeness"])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("has no matching dataset metric", proc.stdout)

    def test_validate_completeness_passes_complete_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            proc = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate", "--completeness"])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_metadata_refine_build_reference_pack_without_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            csv_path = workspace / "sample.csv"
            profile_path = workspace / "profile.json"
            csv_path.write_text("a,b\n1,x\n", encoding="utf-8")
            profile_path.write_text(json.dumps({"schema": {"columns": [{"name": "a", "role": "metric"}]}}), encoding="utf-8")
            proc = self.run_cmd(
                [
                    sys.executable,
                    str(REFINE_BUILD),
                    "--workspace",
                    str(workspace),
                    "--dataset-id",
                    "test.dataset",
                    "--data-csv",
                    str(csv_path),
                    "--profile-json",
                    str(profile_path),
                    "--refine-id",
                    "refine-test",
                ]
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            manifest = json.loads((workspace / "runtime" / "metadata-refine" / "refine-test" / "evidence_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["dataset_id"], "test.dataset")
            self.assertEqual(manifest["inputs"]["data_csv"], "sample.csv")

    def test_duckdb_exporter_help_not_shadowed_by_workspace_duckdb_dir(self) -> None:
        proc = self.run_cmd([sys.executable, str(DUCKDB_EXPORTER), "--help"], cwd=REPO)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Controlled export", proc.stdout)

    def test_duckdb_metadata_report_uses_metric_definition_for_metric_source_field(self) -> None:
        script_dir = str(DUCKDB_REPORTER.parent)
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        spec = importlib.util.spec_from_file_location("generate_sync_report_for_test", DUCKDB_REPORTER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        dataset = {
            "id": "test.duckdb.issue1",
            "display_name": "Issue 1 Dataset",
            "source": {"connector": "duckdb"},
            "fields": [
                {
                    "name": "profit",
                    "display_name": "Profit",
                    "role": "metric_source",
                    "type": "number",
                    "business_definition": {
                        "text": "Field pending definition",
                        "source_type": "generated",
                        "confidence": 0.2,
                        "needs_review": True,
                    },
                }
            ],
            "metrics": [
                {
                    "name": "profit",
                    "display_name": "Profit",
                    "expression": "SUM(profit)",
                    "aggregation": "sum",
                    "source_mapping": {"view_field": "profit"},
                    "business_definition": definition("Metric confirmed definition"),
                }
            ],
        }

        report = module.render_yaml_metadata_report(
            dataset=dataset,
            mapping=None,
            generated_at=datetime(2026, 4, 30),
            report_dir=Path("/tmp/ra-test-reports"),
            step_results={"validate": "success"},
        )

        self.assertIn("Metric confirmed definition", report)
        self.assertIn("已确认（置信度 0.9）", report)
        self.assertNotIn("Field pending definition", report)
        self.assertIn("- 无待确认字段或指标。", report)


if __name__ == "__main__":
    unittest.main()
