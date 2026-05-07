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
METADATA_REPORTER = REPO / "skills" / "metadata-report" / "scripts" / "generate_report.py"
DUCKDB_REPORTER = REPO / "skills" / "metadata-report" / "scripts" / "duckdb_report.py"
TABLEAU_REPORTER = REPO / "skills" / "metadata-report" / "scripts" / "tableau_report.py"
DUCKDB_LEGACY_REPORTER = REPO / "skills" / "metadata" / "adapters" / "duckdb" / "scripts" / "generate_sync_report.py"
TABLEAU_LEGACY_REPORTER = REPO / "skills" / "metadata" / "adapters" / "tableau" / "scripts" / "generate_sync_report.py"
TABLEAU_BOOTSTRAP = REPO / "skills" / "metadata" / "adapters" / "tableau" / "scripts" / "_bootstrap.py"
SYNC_REGISTRY = REPO / "skills" / "metadata" / "scripts" / "sync_registry.py"
SQLITE_STORE = REPO / "runtime" / "tableau" / "sqlite_store.py"


def load_script(path: Path, module_name: str):
    script_dir = str(path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_adapter_wrapper(path: Path, module_name: str):
    old_path = list(sys.path)
    old_bootstrap = sys.modules.pop("_bootstrap", None)
    try:
        sys.path.insert(0, str(path.parent))
        return load_script(path, module_name)
    finally:
        sys.path[:] = old_path
        if old_bootstrap is not None:
            sys.modules["_bootstrap"] = old_bootstrap
        else:
            sys.modules.pop("_bootstrap", None)


def definition(text: str = "已确认业务定义") -> dict:
    return {
        "text": text,
        "source_type": "user_confirmed",
        "confidence": 0.9,
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

    def test_validate_blocks_dataset_runtime_and_mapping_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            path = workspace / "metadata" / "datasets" / "test.dataset.yaml"
            dataset = yaml.safe_load(path.read_text(encoding="utf-8"))
            dataset["fields"][0]["sample_profile"] = {"null_count": 0}
            dataset["fields"][0]["enum_values"] = ["A", "B"]
            dataset["fields"][0]["source_mapping"] = {"view_field": "metric_field_0"}
            dataset["fields"][0]["definition_source"] = "mapping_override"
            dataset["fields"][0]["source_evidence"] = [{"type": "test", "source": "tests"}]
            dataset["fields"][0]["business_definition"]["source_evidence"] = [{"type": "test", "source": "tests"}]
            dataset["fields"][0]["business_definition"]["quote"] = "fixture"
            path.write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")

            proc = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate"])

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("sample_profile", proc.stdout)
            self.assertIn("enum_values", proc.stdout)
            self.assertIn("source_mapping", proc.stdout)
            self.assertIn("definition_source", proc.stdout)
            self.assertIn("dataset field/metric definitions must use business_definition.ref", proc.stdout)
            self.assertIn("dataset definitions must use ref instead of expanded evidence", proc.stdout)
            self.assertIn("audit quotes belong", proc.stdout)

    def test_validate_blocks_duplicate_description_and_definition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            path = workspace / "metadata" / "datasets" / "test.dataset.yaml"
            dataset = yaml.safe_load(path.read_text(encoding="utf-8"))
            dataset["fields"][0]["description"] = "Duplicated definition."
            dataset["fields"][0]["business_definition"]["text"] = "Duplicated definition."
            path.write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")

            proc = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate"])

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("business definition must not duplicate description", proc.stdout)

    def test_validate_blocks_pending_formal_metric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            path = workspace / "metadata" / "datasets" / "test.dataset.yaml"
            dataset = yaml.safe_load(path.read_text(encoding="utf-8"))
            dataset["metrics"][0]["business_definition"] = {
                "text": "业务定义待确认",
                "source_type": "pending",
                "confidence": 0.0,
                "needs_review": True,
            }
            path.write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")

            proc = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate"])

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("pending definitions must not be registered as formal metrics", proc.stdout)

    def test_validate_warns_for_large_but_clean_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            path = workspace / "metadata" / "datasets" / "test.dataset.yaml"
            dataset = yaml.safe_load(path.read_text(encoding="utf-8"))
            dataset["business"]["sample_questions"] = [f"question {index}" for index in range(1100)]
            path.write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")

            proc = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate"])

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("warnings", proc.stdout)
            self.assertIn("dataset YAML has", proc.stdout)

    def test_enrich_definitions_removes_dataset_payload_leaks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            path = workspace / "metadata" / "datasets" / "test.dataset.yaml"
            dataset = yaml.safe_load(path.read_text(encoding="utf-8"))
            dataset["fields"][0]["sample_profile"] = {"null_count": 0}
            dataset["fields"][0]["enum_values"] = ["A"]
            dataset["fields"][0]["source_mapping"] = {"view_field": "metric_field_0"}
            dataset["fields"][0]["definition_source"] = "mapping_override"
            dataset["fields"][0]["source_evidence"] = [{"type": "test", "source": "tests"}]
            dataset["fields"][0]["business_definition"]["source_evidence"] = [{"type": "test", "source": "tests"}]
            dataset["fields"][0]["business_definition"]["quote"] = "fixture"
            dataset["fields"][0]["business_definition"]["source"] = "metadata/sources/refine/test/evidence.json"
            dataset["fields"][0]["business_definition"]["document_path"] = "metadata/sources/refine/test/source.md"
            dataset["fields"][0]["duckdb_type"] = "INTEGER"
            dataset["fields"][0]["nullable"] = False
            path.write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")

            enrich = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "enrich-definitions", "--dataset-id", "test.dataset"])
            self.assertEqual(enrich.returncode, 0, enrich.stdout + enrich.stderr)
            validate = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate"])

            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
            cleaned = yaml.safe_load(path.read_text(encoding="utf-8"))
            field = cleaned["fields"][0]
            for key in ("sample_profile", "enum_values", "source_mapping", "definition_source", "source_evidence", "duckdb_type", "nullable"):
                self.assertNotIn(key, field)
            for key in ("source_evidence", "quote", "source", "document_path"):
                self.assertNotIn(key, field["business_definition"])
            self.assertEqual(field["business_definition"]["source_type"], "user_confirmed")

    def test_enrich_definitions_uses_ref_without_copying_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=0)
            path = workspace / "metadata" / "datasets" / "test.dataset.yaml"
            dataset = yaml.safe_load(path.read_text(encoding="utf-8"))
            dataset["fields"][0]["business_definition"] = {
                "text": "业务定义待确认",
                "source_type": "pending",
                "confidence": 0.0,
                "needs_review": True,
            }
            dataset["dictionary_refs"] = ["test.dictionary"]
            path.write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")
            dictionary = {
                "version": 1,
                "id": "test.dictionary",
                "kind": "dictionary",
                "display_name": "Test Dictionary",
                "source_evidence": [{"type": "test", "source": "tests", "quote": "fixture"}],
                "fields": [
                    {
                        "name": "metric_field_0",
                        "display_name": "metric_field_0",
                        "role": "metric_source",
                        "type": "number",
                        "description": "Dictionary source field.",
                        "business_definition": {
                            "text": "Dictionary confirmed field definition.",
                            "source_type": "dictionary",
                            "confidence": 0.9,
                            "source_evidence": [{"type": "test", "source": "tests", "quote": "fixture"}],
                            "needs_review": False,
                        },
                    }
                ],
            }
            (workspace / "metadata" / "dictionaries" / "test.dictionary.yaml").write_text(
                yaml.safe_dump(dictionary, allow_unicode=True), encoding="utf-8"
            )

            enrich = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "enrich-definitions", "--dataset-id", "test.dataset"])
            self.assertEqual(enrich.returncode, 0, enrich.stdout + enrich.stderr)

            cleaned = yaml.safe_load(path.read_text(encoding="utf-8"))
            definition_payload = cleaned["fields"][0]["business_definition"]
            self.assertEqual(definition_payload["source_type"], "dictionary")
            self.assertEqual(definition_payload["ref"], "test.dictionary.metric_field_0")
            self.assertNotIn("source_evidence", definition_payload)

    def test_record_relation_writes_audit_ref_association(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            proc = self.run_cmd(
                [
                    sys.executable,
                    str(METADATA),
                    "--workspace",
                    str(workspace),
                    "record-relation",
                    "--ref",
                    "test.dictionary.metric_field_0",
                    "--dataset-id",
                    "test.dataset",
                    "--section",
                    "fields",
                    "--name",
                    "metric_field_0",
                    "--source-type",
                    "dictionary",
                    "--target",
                    "metadata/dictionaries/test.dictionary.yaml",
                    "--evidence",
                    "metadata/sources/refine/refine-test/evidence_manifest.json",
                    "--reason",
                    "dictionary definition linked by ref",
                ]
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["relation_count"], 1)
            relation_path = workspace / "metadata" / "audit" / "metadata_relations.jsonl"
            report_path = workspace / "metadata" / "audit" / "metadata_change_report.md"
            relation = json.loads(relation_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(relation["ref"], "test.dictionary.metric_field_0")
            self.assertEqual(relation["targets"], ["metadata/dictionaries/test.dictionary.yaml"])
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("relation_count: 1", report)
            self.assertIn("test.dictionary.metric_field_0", report)

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
        module = load_script(DUCKDB_REPORTER, "duckdb_report_for_test")

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
            mapping={
                "mappings": [
                    {
                        "view_field": "cnf",
                        "type": "metric",
                        "standard_id": "cnf",
                        "notes": "Cnf 在该数据源中作为指标候选字段使用；具体业务口径需确认。",
                    }
                ]
            },
            generated_at=datetime(2026, 4, 30),
            report_dir=Path("/tmp/ra-test-reports"),
            step_results={"validate": "success"},
        )

        self.assertIn("Metric confirmed definition", report)
        self.assertIn("已确认（置信度 0.9）", report)
        self.assertNotIn("Field pending definition", report)
        self.assertIn("- 无显式待补齐项。", report)

    def test_duckdb_metadata_report_pending_definition_matches_tableau_default(self) -> None:
        module = load_script(DUCKDB_REPORTER, "duckdb_report_pending_default_test")

        dataset = {
            "id": "test.duckdb.pending",
            "display_name": "Pending Dataset",
            "source": {"connector": "duckdb"},
            "fields": [
                {
                    "name": "cnf",
                    "display_name": "Cnf",
                    "role": "metric_source",
                    "type": "number",
                    "description": "Cnf 在该数据源中作为指标候选字段使用；具体业务口径需确认。",
                    "business_definition": {
                        "text": "Cnf 在该数据源中作为指标候选字段使用；具体业务口径需确认。",
                        "source_type": "industry_draft",
                        "confidence": 0.65,
                        "needs_review": True,
                    },
                }
            ],
            "metrics": [],
        }

        report = module.render_yaml_metadata_report(
            dataset=dataset,
            mapping=None,
            generated_at=datetime(2026, 4, 30),
            report_dir=Path("/tmp/ra-test-reports"),
            step_results={"validate": "success"},
        )

        self.assertIn("业务定义待确认", report)
        self.assertNotIn("`pending`", report)
        self.assertIn("待补齐（置信度 0.65）", report)
        self.assertNotIn("在该数据源中作为指标候选字段使用", report)

        no_mapping_report = module.render_yaml_metadata_report(
            dataset=dataset,
            mapping=None,
            generated_at=datetime(2026, 4, 30),
            report_dir=Path("/tmp/ra-test-reports"),
            step_results={"validate": "success"},
        )
        self.assertNotIn("- 待补充映射。", no_mapping_report)

    def test_metadata_report_does_not_use_description_as_definition(self) -> None:
        module = load_script(DUCKDB_REPORTER, "duckdb_report_missing_definition_test")

        dataset = {
            "id": "test.duckdb.description",
            "display_name": "Description Dataset",
            "source": {"connector": "duckdb"},
            "fields": [
                {
                    "name": "region",
                    "display_name": "Region",
                    "role": "dimension",
                    "type": "string",
                    "description": "Short field note that is not a business definition.",
                    "business_definition": {},
                }
            ],
            "metrics": [],
        }

        report = module.render_yaml_metadata_report(
            dataset=dataset,
            mapping=None,
            generated_at=datetime(2026, 4, 30),
            report_dir=Path("/tmp/ra-test-reports"),
            step_results={"validate": "success"},
        )

        self.assertNotIn("Short field note that is not a business definition.", report)
        self.assertIn("仅结构可用", report)
        self.assertIn("metadata/datasets/test.duckdb.description.yaml::fields[name=region].business_definition.text", report)

    def test_duckdb_metadata_report_collapses_datetime_samples_to_regex(self) -> None:
        module = load_script(DUCKDB_REPORTER, "duckdb_report_pattern_test")

        formatted = module._format_sample_values_with_pattern(
            ["2026-04-15 00:00:00", "2026-04-16 00:00:00", "2026-04-17 00:00:00"]
        )

        self.assertEqual(formatted.count("2026-04-"), 1)
        self.assertIn(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", formatted)

    def test_sync_registry_writes_time_field_regex_validation(self) -> None:
        module = load_script(SYNC_REGISTRY, "sync_registry_pattern_test")

        dataset = {
            "version": 1,
            "id": "test.datetime",
            "display_name": "Datetime Dataset",
            "source": {"connector": "duckdb", "object": "main.orders"},
            "business": {"time_fields": ["order_time"]},
            "maintenance": {},
            "fields": [
                {
                    "name": "order_time",
                    "display_name": "Order Time",
                    "role": "time_dimension",
                    "type": "datetime",
                    "description": "Order timestamp.",
                    "business_definition": definition("Order timestamp definition"),
                }
            ],
            "metrics": [],
        }

        _entry, spec = module.build_entry_and_spec(dataset)

        self.assertEqual(
            spec["filters"][0]["validation"]["pattern"],
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",
        )
        self.assertEqual(spec["dimensions"][0]["validation"]["example"], "2026-04-15 00:00:00")

    def test_tableau_metadata_report_uses_yaml_review_and_tableau_controls(self) -> None:
        module = load_script(TABLEAU_REPORTER, "tableau_report_for_test")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            module.WORKSPACE_DIR = workspace
            (workspace / "metadata" / "datasets").mkdir(parents=True)
            (workspace / "metadata" / "mappings").mkdir(parents=True)
            dataset = {
                "version": 1,
                "id": "tableau.test.view",
                "display_name": "Tableau Test View",
                "description": "测试 Tableau 视图。",
                "source": {"connector": "tableau"},
                "business": {
                    "grain": ["period_key"],
                    "time_fields": ["start_date"],
                    "suitable_for": ["测试分析"],
                    "not_suitable_for": ["替代底层事实表"],
                },
                "maintenance": {
                    "source_evidence": [{"type": "sync_report", "source": "metadata/sync/tableau/reports/test.md"}],
                    "pending_questions": ["确认 Tableau 计算字段口径。"],
                },
                "mapping_ref": "tableau.test.view.mapping",
                "fields": [
                    {
                        "name": "travel_month",
                        "source_field": "period_key",
                        "display_name": "period_key",
                        "role": "time_dimension",
                        "type": "date",
                        "business_definition": {
                            "text": "已确认的周期字段定义。",
                            "source_type": "user_confirmed",
                            "ref": "metadata/audit/metadata_relations.jsonl#field-period",
                            "confidence": 0.8,
                            "source_evidence": [{"type": "sync_report", "source": "metadata/sync/tableau/reports/test.md"}],
                            "needs_review": False,
                        },
                    }
                ],
                "metrics": [
                    {
                        "name": "passenger_count",
                        "source_field": "measure_value",
                        "display_name": "measure_value",
                        "expression": "SUM(`measure_value`)",
                        "aggregation": "sum",
                        "unit": "人",
                        "business_definition": {
                            "text": "待补齐的指标定义。",
                            "source_type": "industry_draft",
                            "ref": "metadata/audit/metadata_relations.jsonl#metric-measure",
                            "confidence": 0.6,
                            "source_evidence": [{"type": "sync_report", "source": "metadata/sync/tableau/reports/test.md"}],
                            "needs_review": True,
                        },
                    }
                ],
            }
            mapping = {
                "version": 1,
                "id": "tableau.test.view.mapping",
                "source_id": "tableau.test.view",
                "mappings": [
                    {
                        "type": "metric",
                        "view_field": "measure_value",
                        "standard_id": "passenger_count",
                        "field_id_or_override": "passenger_count",
                        "definition_override": "指标定义待补齐。",
                    }
                ],
            }
            (workspace / "metadata" / "datasets" / "tableau.test.view.yaml").write_text(
                yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8"
            )
            (workspace / "metadata" / "mappings" / "tableau.test.view.mapping.yaml").write_text(
                yaml.safe_dump(mapping, allow_unicode=True), encoding="utf-8"
            )

            report = module.render_sync_report(
                entry={
                    "source_id": "tableau.test.view",
                    "key": "test.view",
                    "type": "view",
                    "status": "active",
                    "category": "test",
                    "display_name": "Tableau Test View",
                    "tableau": {
                        "view_luid": "view-1",
                        "view_name": "测试视图",
                        "content_url": "Workbook/sheets/View",
                    },
                },
                spec={
                    "dimensions": [{"name": "period_key", "data_type": "date"}],
                    "measures": [{"name": "measure_value", "data_type": "integer"}],
                    "filters": [{"tableau_field": "period_key", "sample_values": ["2026-04"]}],
                    "parameters": [{"tableau_field": "start_date"}],
                },
                context={"unresolved_dimensions": []},
                generated_at=datetime(2026, 4, 30),
                report_dir=workspace / "metadata" / "sync" / "tableau" / "reports",
                with_samples=True,
                sync_mode="live",
                step_results={"fields": "success", "filters": "success", "registry": "success"},
                export_summary=None,
                manifest=None,
            )

        self.assertIn("metadata/datasets/*.yaml", report)
        self.assertIn("作为报告元数据事实读取", report)
        self.assertIn("已确认的周期字段定义。", report)
        self.assertIn("业务定义待确认", report)
        self.assertNotIn("`pending`", report)
        self.assertNotIn("待补齐的指标定义。", report)
        self.assertIn("待补齐（置信度 0.6）", report)
        self.assertIn("## 5. 元数据补齐清单", report)
        self.assertIn("### 7.1 字段明细", report)
        self.assertIn("### 7.2 指标明细", report)
        self.assertIn("## 8. 数据源使用说明", report)
        self.assertIn("`--vf`", report)
        self.assertIn("`--vp`", report)
        self.assertNotIn("常见用途", report)
        self.assertNotIn("使用建议", report)
        self.assertNotIn("适合做", report)
        self.assertNotIn("先补齐业务定义，再用于正式结论", report)
        self.assertNotIn("作为指标来源字段使用", report)
        self.assertNotIn("来源摘要", report)
        self.assertNotIn("字段名证据", report)
        self.assertNotIn("指标表达式", report)
        self.assertNotIn("来源字段", report)
        self.assertIn("定义位置", report)
        self.assertIn("metadata/datasets/tableau.test.view.yaml::fields[name=travel_month].business_definition", report)
        self.assertIn("metadata/datasets/tableau.test.view.yaml::metrics[name=passenger_count].business_definition", report)
        self.assertIn("metadata/audit/*", report)
        self.assertIn("审计层隔离，不作为业务定义真源", report)
        self.assertNotIn("metadata/audit/metadata_relations.jsonl#field-period", report)
        self.assertNotIn("metadata/audit/metadata_relations.jsonl#metric-measure", report)
        self.assertNotIn("industry_draft", report)
        self.assertIn("SUM(measure_value)", report)
        self.assertNotIn("SUM(`measure_value`)", report)
        self.assertNotIn("`measure_value`)", report)
        self.assertIn("未提供 manifest", report)
        self.assertNotIn("指标定义待补齐。", report)
        self.assertTrue(module.build_report_filename("tableau.test.view", generated_at=datetime(2026, 4, 30)).endswith("_metadata_report.md"))

    def test_metadata_report_unified_cli_generates_duckdb_yaml_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            proc = self.run_cmd(
                [
                    sys.executable,
                    str(METADATA_REPORTER),
                    "--workspace",
                    str(workspace),
                    "--connector",
                    "duckdb",
                    "--dataset-id",
                    "test.dataset",
                ]
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("[OK] report ->", proc.stdout)
            reports = list((workspace / "metadata" / "sync" / "duckdb" / "reports").glob("*test.dataset_metadata_report.md"))
            self.assertEqual(len(reports), 1)
            content = reports[0].read_text(encoding="utf-8")
            self.assertIn("### 7.1 字段明细", content)
            self.assertIn("## 5. 元数据补齐清单", content)
            self.assertNotIn("常见用途", content)
            self.assertNotIn("使用建议", content)
            self.assertNotIn("适合做", content)
            self.assertNotIn("先补齐业务定义，再用于正式结论", content)
            self.assertNotIn("作为指标来源字段使用", content)
            self.assertNotIn("来源摘要", content)
            self.assertNotIn("字段名证据", content)
            self.assertNotIn("指标表达式", content)
            self.assertNotIn("来源字段", content)
            self.assertIn("定义位置", content)
            self.assertIn("metadata/datasets/test.dataset.yaml::fields[name=year].business_definition", content)
            self.assertIn("metadata/datasets/test.dataset.yaml::metrics[name=metric_field_0].business_definition", content)
            self.assertIn("metadata/audit/*", content)
            self.assertIn("审计层隔离，不作为业务定义真源", content)
            self.assertNotIn("industry_draft", content)

    def test_metadata_report_renderer_modules_are_internal_only(self) -> None:
        for path, connector in [(DUCKDB_REPORTER, "duckdb"), (TABLEAU_REPORTER, "tableau")]:
            proc = self.run_cmd([sys.executable, str(path), "--help"])
            output = proc.stdout + proc.stderr
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("generate_report.py", output)
            self.assertIn(connector, output)

    def test_adapter_sync_scripts_no_longer_generate_reports(self) -> None:
        for path in [
            REPO / "skills" / "metadata" / "adapters" / "duckdb" / "scripts" / "sync_all.py",
            REPO / "skills" / "metadata" / "adapters" / "tableau" / "scripts" / "sync_all.py",
        ]:
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("generate_sync_report.py", content)
            self.assertIn("metadata-report", content)

    def test_adapter_generate_sync_report_scripts_are_wrappers_only(self) -> None:
        for path, connector in [
            (DUCKDB_LEGACY_REPORTER, "duckdb"),
            (TABLEAU_LEGACY_REPORTER, "tableau"),
        ]:
            content = path.read_text(encoding="utf-8")
            self.assertIn("RA:metadata-report", content)
            self.assertIn("generate_report.py", content)
            self.assertIn(f'"{connector}"', content)
            self.assertNotIn("def render_sync_report", content)
            self.assertNotIn("write_text", content)
            self.assertNotIn("Sync Report", content)
            self.assertNotIn("建议补充的业务描述", content)
            self.assertNotIn("使用建议", content)

    def test_adapter_generate_sync_report_main_delegates_to_metadata_report(self) -> None:
        cases = [
            (DUCKDB_LEGACY_REPORTER, "duckdb", ["--key", "legacy.duckdb"], "legacy.duckdb.source"),
            (
                TABLEAU_LEGACY_REPORTER,
                "tableau",
                [
                    "--key",
                    "legacy.tableau",
                    "--with-samples",
                    "--export-summary",
                    "summary.json",
                    "--manifest",
                    "manifest.json",
                ],
                "legacy.tableau",
            ),
        ]
        for path, connector, argv, expected_dataset_id in cases:
            module = load_adapter_wrapper(path, f"{connector}_legacy_report_wrapper_test")
            module._report_script = lambda: METADATA_REPORTER
            if connector == "duckdb":
                module._source_id_for_key = lambda key: f"{key}.source"

            calls: list[list[str]] = []

            class Completed:
                returncode = 7

            def fake_run(command: list[str]) -> Completed:
                calls.append(command)
                return Completed()

            old_argv = sys.argv
            old_run = module.subprocess.run
            module.subprocess.run = fake_run
            try:
                sys.argv = [str(path), *argv]
                with self.assertRaises(SystemExit) as raised:
                    module.main()
            finally:
                sys.argv = old_argv
                module.subprocess.run = old_run

            self.assertEqual(raised.exception.code, 7)
            self.assertEqual(len(calls), 1)
            command = calls[0]
            self.assertEqual(Path(command[1]), METADATA_REPORTER)
            self.assertEqual(command[command.index("--connector") + 1], connector)
            self.assertEqual(command[command.index("--dataset-id") + 1], expected_dataset_id)
            if connector == "tableau":
                self.assertIn("--with-samples", command)
                self.assertEqual(command[command.index("--export-summary") + 1], "summary.json")
                self.assertEqual(command[command.index("--manifest") + 1], "manifest.json")

    def test_sqlite_store_save_entry_replaces_existing_source_id(self) -> None:
        module = load_script(SQLITE_STORE, "sqlite_store_upsert_test")

        with tempfile.TemporaryDirectory() as tmp:
            module._DB_PATH = Path(tmp) / "runtime" / "registry.db"
            module.save_entry(
                {
                    "key": "old.key",
                    "source_id": "tableau.test.view",
                    "type": "view",
                    "status": "active",
                    "category": "old",
                    "display_name": "Old",
                }
            )
            module.save_entry(
                {
                    "key": "new.key",
                    "source_id": "tableau.test.view",
                    "type": "view",
                    "status": "active",
                    "category": "new",
                    "display_name": "New",
                }
            )
            document = module.load_registry_document()

        entries = document["entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["key"], "new.key")
        self.assertEqual(document["category_index"]["new"]["entries"], ["new.key"])
        self.assertNotIn("old.key", document["category_index"].get("old", {}).get("entries", []))

    def test_tableau_bootstrap_finds_data_export_tableau_scripts(self) -> None:
        module = load_script(TABLEAU_BOOTSTRAP, "tableau_bootstrap_for_test")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            expected = workspace / "skills" / "data-export" / "scripts" / "tableau"
            expected.mkdir(parents=True)

            self.assertEqual(module._find_tableau_scripts_dir(workspace), expected)


if __name__ == "__main__":
    unittest.main()
