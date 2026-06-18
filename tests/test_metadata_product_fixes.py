from __future__ import annotations

import json
import importlib.util
import builtins
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[1]
METADATA = REPO / "skills" / "metadata" / "scripts" / "metadata.py"
GETTING_STARTED_DOCTOR = REPO / "skills" / "getting-started" / "scripts" / "doctor.py"
SCRIPT_PY = REPO / "scripts" / "py"
ANALYSIS_INIT_JOB = REPO / "skills" / "analysis-run" / "scripts" / "init_or_resume_job.py"
REFINE_BUILD = REPO / "skills" / "metadata-refine" / "scripts" / "build_reference_pack.py"
DUCKDB_EXPORTER = REPO / "skills" / "data-export" / "scripts" / "duckdb" / "export_duckdb_source.py"
MYSQL_EXPORTER = REPO / "skills" / "data-export" / "scripts" / "mysql" / "export_mysql_source.py"
MYSQL_EXPORT_WRAPPER = REPO / "skills" / "data-export" / "scripts" / "mysql" / "mysql_export_with_meta.py"
CLICKHOUSE_EXPORTER = REPO / "skills" / "data-export" / "scripts" / "clickhouse" / "export_clickhouse_source.py"
CLICKHOUSE_EXPORT_WRAPPER = REPO / "skills" / "data-export" / "scripts" / "clickhouse" / "clickhouse_export_with_meta.py"
SQL_EXPORT_COMMON = REPO / "skills" / "data-export" / "scripts" / "sql" / "common_sql_export.py"
MYSQL_DISCOVER = REPO / "skills" / "metadata" / "adapters" / "mysql" / "scripts" / "discover_catalog.py"
CLICKHOUSE_DISCOVER = REPO / "skills" / "metadata" / "adapters" / "clickhouse" / "scripts" / "discover_catalog.py"
SOURCE_CONTEXT = REPO / "runtime" / "tableau" / "source_context.py"
REFINE_PROBE = REPO / "skills" / "metadata-refine" / "scripts" / "probe_data.py"
REFINE_RESOLVE_GAPS = REPO / "skills" / "metadata-refine" / "scripts" / "resolve_report_gaps.py"
METADATA_REPORTER = REPO / "skills" / "metadata-report" / "scripts" / "generate_report.py"
METADATA_REPORT_BOOTSTRAP = REPO / "skills" / "metadata-report" / "scripts" / "_bootstrap.py"
DUCKDB_REPORTER = REPO / "skills" / "metadata-report" / "scripts" / "duckdb_report.py"
TABLEAU_REPORTER = REPO / "skills" / "metadata-report" / "scripts" / "tableau_report.py"
DUCKDB_LEGACY_REPORTER = REPO / "skills" / "metadata" / "adapters" / "duckdb" / "scripts" / "generate_sync_report.py"
TABLEAU_LEGACY_REPORTER = REPO / "skills" / "metadata" / "adapters" / "tableau" / "scripts" / "generate_sync_report.py"
TABLEAU_BOOTSTRAP = REPO / "skills" / "metadata" / "adapters" / "tableau" / "scripts" / "_bootstrap.py"
SYNC_REGISTRY = REPO / "skills" / "metadata" / "scripts" / "sync_registry.py"
SQLITE_STORE = REPO / "runtime" / "tableau" / "sqlite_store.py"
DATA_ANALYTICS_SEMANTIC_EXPORTER = REPO / "skills" / "data-analytics-semantic-export" / "scripts" / "export_semantic_layer.py"
INSTALLER = REPO / "scripts" / "install_codex_plugin.py"
DELIVERY_MANIFEST = REPO / "skills" / "report-verify" / "scripts" / "build_delivery_manifest.py"


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
                "physical_name": name,
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
            "physical_name": "year",
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


def write_sql_dataset(workspace: Path, connector: str) -> None:
    dataset = {
        "version": 1,
        "id": f"{connector}.test.orders",
        "display_name": f"{connector} orders",
        "description": "SQL orders test dataset.",
        "source": {
            "connector": connector,
            "object": "analytics.orders",
            connector: {
                "database": "analytics",
                "schema": "analytics" if connector == "mysql" else "",
                "table": "orders",
                "object_name": "orders",
                "object_kind": "table",
                "connection_ref": f"{connector.upper()}_CONNECTION_JSON",
            },
        },
        "business": {"grain": ["order_id"], "primary_key": ["order_id"], "time_fields": ["order_date"], "suitable_for": [], "not_suitable_for": [], "sample_questions": []},
        "maintenance": {"owner": "test", "pending_questions": []},
        "fields": [
            {
                "name": "order_id",
                "display_name": "Order ID",
                "physical_name": "order_id",
                "role": "identifier",
                "type": "string",
                "description": "Order identifier.",
                "business_definition": definition("Order identifier definition"),
            },
            {
                "name": "order_date",
                "display_name": "Order Date",
                "physical_name": "order_date",
                "role": "time_dimension",
                "type": "date",
                "description": "Order date.",
                "business_definition": definition("Order date definition"),
            },
            {
                "name": "region",
                "display_name": "Region",
                "physical_name": "region",
                "role": "dimension",
                "type": "string",
                "description": "Order region.",
                "business_definition": definition("Order region definition"),
            },
            {
                "name": "amount",
                "display_name": "Amount",
                "physical_name": "amount",
                "role": "metric_source",
                "type": "number",
                "description": "Order amount.",
                "business_definition": definition("Order amount field definition"),
            },
        ],
        "metrics": [
            {
                "name": "amount",
                "display_name": "Amount",
                "expression": "SUM(amount)",
                "aggregation": "sum",
                "description": "Order amount metric.",
                "business_definition": definition("Order amount metric definition"),
            }
        ],
    }
    (workspace / "metadata" / "datasets").mkdir(parents=True)
    (workspace / "metadata" / "mappings").mkdir(parents=True)
    (workspace / "metadata" / "dictionaries").mkdir(parents=True)
    (workspace / "metadata" / "datasets" / f"{connector}.test.orders.yaml").write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")


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

    def test_validate_blocks_display_name_pollution_in_field_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            path = workspace / "metadata" / "datasets" / "test.dataset.yaml"
            dataset = yaml.safe_load(path.read_text(encoding="utf-8"))
            dataset["fields"][0]["name"] = "航班性质"
            dataset["fields"][0]["display_name"] = "航班性质"
            dataset["fields"][0]["physical_name"] = "FlightType"
            dataset["fields"][0]["business_definition"]["text"] = "航班在业务统计中的性质分类。"
            path.write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")

            proc = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate"])

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("stable semantic id", proc.stdout)
            self.assertIn("display_name", proc.stdout)

    def test_validate_blocks_legacy_dataset_identity_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            path = workspace / "metadata" / "datasets" / "test.dataset.yaml"
            dataset = yaml.safe_load(path.read_text(encoding="utf-8"))
            dataset["fields"][0]["standard_id"] = "metric_field_0"
            dataset["fields"][0]["source_field"] = "metric_field_0"
            dataset["fields"][0]["aliases"] = ["metric field"]
            dataset["fields"][0]["synonyms"] = ["metric source"]
            dataset["metrics"][0]["source_field"] = "metric_field_0"
            dataset["metrics"][0]["aliases"] = ["metric"]
            dataset["metrics"][0]["synonyms"] = ["metric synonym"]
            path.write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")

            proc = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate"])

            self.assertNotEqual(proc.returncode, 0)
            for key in ("standard_id", "source_field", "aliases", "synonyms"):
                self.assertIn(key, proc.stdout)
            self.assertIn("forbidden in dataset fields", proc.stdout)
            self.assertIn("forbidden in dataset metrics", proc.stdout)

    def test_enrich_definitions_removes_legacy_identity_fields_and_keeps_display_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            path = workspace / "metadata" / "datasets" / "test.dataset.yaml"
            dataset = yaml.safe_load(path.read_text(encoding="utf-8"))
            field = dataset["fields"][0]
            field.pop("physical_name")
            field["source_field"] = "source_metric_field"
            field["display_name"] = "指标字段"
            field["standard_id"] = "metric_field_0"
            field["aliases"] = ["指标字段别名"]
            field["synonyms"] = ["指标字段同义词"]
            metric = dataset["metrics"][0]
            metric["display_name"] = "指标"
            metric["source_field"] = "source_metric_field"
            metric["standard_id"] = "metric_field_0"
            metric["aliases"] = ["指标别名"]
            metric["synonyms"] = ["指标同义词"]
            path.write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")

            enrich = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "enrich-definitions", "--dataset-id", "test.dataset"])
            self.assertEqual(enrich.returncode, 0, enrich.stdout + enrich.stderr)
            cleaned = yaml.safe_load(path.read_text(encoding="utf-8"))

            self.assertEqual(cleaned["fields"][0]["display_name"], "指标字段")
            self.assertEqual(cleaned["fields"][0]["physical_name"], "source_metric_field")
            for key in ("standard_id", "source_field", "aliases", "synonyms"):
                self.assertNotIn(key, cleaned["fields"][0])
                self.assertNotIn(key, cleaned["metrics"][0])

            validate = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate"])
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

    def test_dictionary_aliases_feed_search_and_context_without_dataset_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "metadata" / "datasets").mkdir(parents=True)
            (workspace / "metadata" / "dictionaries").mkdir(parents=True)
            (workspace / "metadata" / "mappings").mkdir(parents=True)
            dataset = {
                "version": 1,
                "id": "test.alias.orders",
                "display_name": "Alias Orders",
                "source": {"connector": "duckdb", "object": "main.orders"},
                "business": {"grain": ["order_id"], "time_fields": [], "suitable_for": [], "not_suitable_for": [], "sample_questions": []},
                "maintenance": {"owner": "test", "pending_questions": []},
                "dictionary_refs": ["test.metrics"],
                "mapping_ref": "test.alias.orders.mapping",
                "fields": [
                    {
                        "name": "ticket_revenue",
                        "display_name": "票款收入",
                        "physical_name": "ticket_revenue",
                        "role": "metric_source",
                        "type": "number",
                        "description": "Ticket revenue field.",
                        "business_definition": definition("Ticket revenue source field definition."),
                    }
                ],
                "metrics": [
                    {
                        "name": "passenger_revenue",
                        "display_name": "客运收入",
                        "expression": "SUM(ticket_revenue)",
                        "aggregation": "sum",
                        "description": "Passenger revenue metric.",
                        "business_definition": {
                            "text": "Passenger revenue definition.",
                            "source_type": "dictionary",
                            "ref": "test.metrics.passenger_revenue",
                            "confidence": 0.9,
                            "needs_review": False,
                        },
                    }
                ],
            }
            dictionary = {
                "version": 1,
                "id": "test.metrics",
                "kind": "dictionary",
                "display_name": "Test Metrics",
                "source_evidence": [{"type": "test", "source": "tests", "quote": "fixture"}],
                "metrics": [
                    {
                        "name": "passenger_revenue",
                        "display_name": "客运收入",
                        "expression": "SUM(ticket_revenue)",
                        "description": "Passenger revenue metric.",
                        "aliases": ["客收", "旅客运输收入"],
                        "synonyms": ["票款收入同义词"],
                        "business_definition": {
                            "text": "Passenger revenue definition.",
                            "source_type": "dictionary",
                            "confidence": 0.9,
                            "source_evidence": [{"type": "test", "source": "tests", "quote": "fixture"}],
                            "needs_review": False,
                        },
                    }
                ],
                "glossary": [
                    {
                        "section": "revenue",
                        "key": "revenue_term",
                        "display_name": "收入术语",
                        "definition": "Revenue term definition.",
                        "synonyms": ["收入同义词"],
                        "business_definition": {
                            "text": "Revenue term definition.",
                            "source_type": "dictionary",
                            "confidence": 0.9,
                            "source_evidence": [{"type": "test", "source": "tests", "quote": "fixture"}],
                            "needs_review": False,
                        },
                    }
                ],
            }
            mapping = {
                "version": 1,
                "id": "test.alias.orders.mapping",
                "kind": "mapping",
                "source_id": "test.alias.orders",
                "display_name": "Alias Orders Mapping",
                "source_evidence": [{"type": "test", "source": "tests", "quote": "fixture"}],
                "mappings": [{"type": "metric", "view_field": "ticket_revenue", "standard_id": "passenger_revenue"}],
            }
            (workspace / "metadata" / "datasets" / "test.alias.orders.yaml").write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")
            (workspace / "metadata" / "dictionaries" / "test.metrics.yaml").write_text(yaml.safe_dump(dictionary, allow_unicode=True), encoding="utf-8")
            (workspace / "metadata" / "mappings" / "test.alias.orders.mapping.yaml").write_text(yaml.safe_dump(mapping, allow_unicode=True), encoding="utf-8")

            validate = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate"])
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
            index = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "index"])
            self.assertEqual(index.returncode, 0, index.stdout + index.stderr)
            search = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "search", "--type", "metric", "--query", "客收"])
            self.assertEqual(search.returncode, 0, search.stdout + search.stderr)
            match = json.loads(search.stdout)["matches"][0]
            self.assertEqual(match["record_type"], "alias")
            self.assertEqual(match["matched_alias"], "客收")
            self.assertEqual(match["canonical_name"], "passenger_revenue")
            self.assertEqual(match["canonical_display_name"], "客运收入")
            self.assertEqual(match["physical_name"], "ticket_revenue")
            self.assertEqual(match["ref"], "test.metrics.passenger_revenue")
            self.assertEqual(match["semantic_ref_status"], "standard_ref")
            self.assertEqual(match["semantic_ref_label"], "标准定义引用")
            self.assertEqual(match["semantic_ref"]["status"], "standard_ref")

            metric_search = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "search", "--type", "metric", "--query", "passenger_revenue", "--limit", "10"])
            self.assertEqual(metric_search.returncode, 0, metric_search.stdout + metric_search.stderr)
            metric_match = next(item for item in json.loads(metric_search.stdout)["matches"] if item.get("dataset_id") == "test.alias.orders" and item.get("record_type") == "metric")
            self.assertEqual(metric_match["semantic_ref_status"], "standard_ref")
            self.assertEqual(metric_match["semantic_ref_label"], "标准定义引用")

            synonym_search = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "search", "--type", "metric", "--query", "票款收入同义词"])
            self.assertEqual(synonym_search.returncode, 0, synonym_search.stdout + synonym_search.stderr)
            synonym_match = json.loads(synonym_search.stdout)["matches"][0]
            self.assertEqual(synonym_match["record_type"], "alias")
            self.assertEqual(synonym_match["matched_alias"], "票款收入同义词")
            self.assertEqual(synonym_match["canonical_name"], "passenger_revenue")
            glossary_search = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "search", "--type", "term", "--query", "收入同义词"])
            self.assertEqual(glossary_search.returncode, 0, glossary_search.stdout + glossary_search.stderr)
            glossary_match = json.loads(glossary_search.stdout)["matches"][0]
            self.assertEqual(glossary_match["record_type"], "alias")
            self.assertEqual(glossary_match["matched_alias"], "收入同义词")
            self.assertEqual(glossary_match["canonical_name"], "revenue_term")

            context = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "context", "--dataset-id", "test.alias.orders", "--metric", "passenger_revenue"])
            self.assertEqual(context.returncode, 0, context.stdout + context.stderr)
            metrics = json.loads(context.stdout)["metrics"]
            dataset_metric = next(item for item in metrics if item["source_layer"] == "dataset")
            self.assertEqual(dataset_metric["canonical_name"], "passenger_revenue")
            self.assertEqual(dataset_metric["canonical_display_name"], "客运收入")
            self.assertEqual(dataset_metric["physical_name"], "ticket_revenue")
            self.assertEqual(dataset_metric["ref"], "test.metrics.passenger_revenue")
            self.assertIn("客收", dataset_metric["aliases"])
            self.assertEqual(dataset_metric["alias_source"], "test.metrics.passenger_revenue")
            self.assertEqual(dataset_metric["semantic_ref"]["status"], "standard_ref")
            self.assertEqual(dataset_metric["semantic_ref"]["label"], "标准定义引用")
            dictionary_metric = next(item for item in metrics if item["source_layer"] == "dictionary")
            self.assertEqual(dictionary_metric["semantic_ref"]["status"], "standard_ref")
            self.assertEqual(dictionary_metric["semantic_ref"]["ref"], "test.metrics.passenger_revenue")

    def test_sync_registry_uses_physical_names_without_metric_source_field(self) -> None:
        sync_module = load_script(SYNC_REGISTRY, "sync_registry_no_source_field_test")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            validate = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate"])
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
            dry_run = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "sync-registry", "--dataset-id", "test.dataset", "--dry-run"])
            self.assertEqual(dry_run.returncode, 0, dry_run.stdout + dry_run.stderr)

            dataset = yaml.safe_load((workspace / "metadata" / "datasets" / "test.dataset.yaml").read_text(encoding="utf-8"))
            entry, spec = sync_module.build_entry_and_spec(dataset)
            self.assertIn("metric_field_0", entry["fields"])
            self.assertEqual(spec["metrics"][0]["name"], "metric_field_0")
            self.assertEqual(spec["metrics"][0]["display_name"], "metric_field_0")
            self.assertNotIn("source_field", spec["metrics"][0])

    def test_getting_started_doctor_reports_fixed_environment_summary(self) -> None:
        proc = self.run_cmd([sys.executable, str(GETTING_STARTED_DOCTOR), "--workspace", str(REPO), "--intent", "analyze"])

        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["workspace"], str(REPO))
        self.assertIn(payload["recommended_next_skill"], {"RA:analysis-run", "RA:metadata"})
        self.assertIn("python_command", payload["environment"])
        self.assertIn("skill_base_dir", payload["environment"])
        self.assertIn("registry_path", payload["environment"])
        self.assertEqual(
            payload["readiness"]["registry_write_allowed_only_via"],
            "skills/metadata/scripts/metadata.py sync-registry",
        )

    def test_scripts_py_maps_source_skill_path_to_installed_skill_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "scripts").mkdir()
            wrapper = workspace / "scripts" / "py"
            wrapper.write_text(SCRIPT_PY.read_text(encoding="utf-8"), encoding="utf-8")
            wrapper.chmod(0o755)
            probe = workspace / ".agents" / "skills" / "probe.py"
            probe.parent.mkdir(parents=True)
            probe.write_text("print('installed-skill-path')\n", encoding="utf-8")

            proc = self.run_cmd([str(wrapper), "skills/probe.py"], cwd=workspace)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "installed-skill-path")

    def test_analysis_init_job_supports_installed_skill_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "runtime").mkdir()
            script = workspace / ".agents" / "skills" / "analysis-run" / "scripts" / "init_or_resume_job.py"
            script.parent.mkdir(parents=True)
            script.write_text(ANALYSIS_INIT_JOB.read_text(encoding="utf-8"), encoding="utf-8")

            proc = self.run_cmd([sys.executable, str(script), "--key", "channel:abc", "--prefix", "discord"], cwd=workspace)

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            session_id = proc.stdout.strip()
            self.assertTrue(session_id.startswith("discord-"))
            self.assertTrue((workspace / "jobs" / session_id / ".meta" / "artifact_index.json").exists())

    def test_getting_started_doctor_reports_duckdb_remediation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "metadata" / "datasets").mkdir(parents=True)
            (workspace / "metadata" / "datasets" / "test.yaml").write_text("id: test\n", encoding="utf-8")
            (workspace / "runtime").mkdir()
            (workspace / "runtime" / "registry.db").write_text("", encoding="utf-8")
            (workspace / ".agents" / "skills" / "metadata" / "scripts").mkdir(parents=True)
            (workspace / ".agents" / "skills" / "metadata" / "scripts" / "metadata.py").write_text("", encoding="utf-8")
            (workspace / "scripts").mkdir()
            scripts_py = workspace / "scripts" / "py"
            scripts_py.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' '{\"python_executable\":\"/tmp/fake-python\",\"dependencies\":{\"yaml\":true,\"duckdb\":false,\"pandas\":true}}'\n",
                encoding="utf-8",
            )
            scripts_py.chmod(0o755)

            proc = self.run_cmd([sys.executable, str(GETTING_STARTED_DOCTOR), "--workspace", str(workspace), "--intent", "analyze"])

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertIn("duckdb Python package missing", " ".join(payload["issues"]))
            expected_remediation = {
                "code": "missing_duckdb_python",
                "command": "./scripts/setup_venv.sh",
                "note": "Install project Python dependencies so ./scripts/py can run DuckDB-backed export wrappers.",
            }
            self.assertIn(
                expected_remediation,
                payload["remediation"],
            )

    def test_getting_started_doctor_reports_missing_shared_lib(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "runtime").mkdir()
            (workspace / "metadata" / "datasets").mkdir(parents=True)
            (workspace / ".agents" / "skills" / "metadata" / "scripts").mkdir(parents=True)
            (workspace / ".agents" / "skills" / "metadata" / "scripts" / "metadata.py").write_text("", encoding="utf-8")
            (workspace / "scripts").mkdir()
            scripts_py = workspace / "scripts" / "py"
            scripts_py.write_text(
                "#!/usr/bin/env bash\n"
                "printf '%s\\n' '{\"python_executable\":\"/tmp/fake-python\",\"dependencies\":{\"yaml\":true,\"duckdb\":true,\"pandas\":true,\"pymysql\":true,\"clickhouse_connect\":true}}'\n",
                encoding="utf-8",
            )
            scripts_py.chmod(0o755)

            proc = self.run_cmd([sys.executable, str(GETTING_STARTED_DOCTOR), "--workspace", str(workspace), "--intent", "start"])

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["environment"]["log_utils_py_exists"])
            self.assertIn("missing_shared_lib", {item["code"] for item in payload["remediation"]})

    def test_installer_copies_project_shared_lib_support(self) -> None:
        installer = load_script(INSTALLER, "realanalyst_installer_lib_test")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()

            installer.install_project_lib(REPO, project, dry_run=False)

            self.assertTrue((project / "lib" / "log_utils.py").exists())

    def test_delivery_manifest_lists_report_and_user_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            job = workspace / "jobs" / "job-001"
            (workspace / "runtime").mkdir()
            (job / ".meta").mkdir(parents=True)
            report = job / "报告_测试_20260618.md"
            csv_file = job / "汇总_测试.csv"
            report.write_text("# 测试报告\n", encoding="utf-8")
            csv_file.write_text("维度,数值\nA,1\n", encoding="utf-8")
            (job / ".meta" / "artifact_index.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {"path": str(report.relative_to(workspace)), "kind": "report", "role": "user"},
                            {"path": str(csv_file.relative_to(workspace)), "kind": "csv", "role": "user"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            env = {**os.environ, "ANALYST_WORKSPACE_DIR": str(workspace)}

            proc = subprocess.run(
                [sys.executable, str(DELIVERY_MANIFEST), "--session-id", "job-001", "--platform", "slack"],
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "ready_for_upload")
            manifest = json.loads((job / "delivery_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["delivery_execution"], "external_gateway")
            delivery_paths = {item["path"] for item in manifest["required_delivery_files"]}
            self.assertIn("jobs/job-001/报告_测试_20260618.md", delivery_paths)
            self.assertIn("jobs/job-001/汇总_测试.csv", delivery_paths)

    def test_delivery_manifest_records_upload_receipt_without_claiming_upload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            job = workspace / "jobs" / "job-002"
            (workspace / "runtime").mkdir()
            job.mkdir(parents=True)
            (job / "报告_测试_20260618.md").write_text("# 测试报告\n", encoding="utf-8")
            receipt = job / "upload_receipt.json"
            receipt.write_text(json.dumps({"success": True, "message_id": "abc123"}), encoding="utf-8")
            env = {**os.environ, "ANALYST_WORKSPACE_DIR": str(workspace)}

            proc = subprocess.run(
                [
                    sys.executable,
                    str(DELIVERY_MANIFEST),
                    "--session-id",
                    "job-002",
                    "--platform",
                    "slack",
                    "--upload-receipt-json",
                    str(receipt),
                ],
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "upload_receipt_recorded")
            manifest = json.loads((job / "delivery_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["delivery_execution"], "external_gateway")

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

    def test_mysql_clickhouse_init_source_and_discovery_help(self) -> None:
        for backend, discover in [("mysql", MYSQL_DISCOVER), ("clickhouse", CLICKHOUSE_DISCOVER)]:
            proc = self.run_cmd(
                [
                    sys.executable,
                    str(METADATA),
                    "init-source",
                    "--backend",
                    backend,
                    "--source-id",
                    f"{backend}.test.orders",
                    "--dry-run",
                ]
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["backend"], backend)
            self.assertIn(f"skills/metadata/adapters/{backend}/scripts/discover_catalog.py", payload["adapter_scripts"])
            self.assertIn("credential_boundary", payload)

            help_proc = self.run_cmd([sys.executable, str(discover), "--help"])
            self.assertEqual(help_proc.returncode, 0, help_proc.stderr)
            self.assertIn("Discover", help_proc.stdout)

            dry_run = self.run_cmd(
                [
                    sys.executable,
                    str(discover),
                    "--source-id",
                    f"{backend}.test.orders",
                    "--database",
                    "analytics",
                    "--table",
                    "orders",
                    "--dry-run",
                ]
            )
            self.assertEqual(dry_run.returncode, 0, dry_run.stdout + dry_run.stderr)
            snapshot = json.loads(dry_run.stdout)
            self.assertEqual(snapshot["connector"], backend)
            self.assertEqual(snapshot["columns"], [])

    def test_metadata_refine_guided_gap_workflow_profiles_real_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            csv_path = workspace / "orders.csv"
            csv_path.write_text(
                "order_id,order_date,region,amount\n"
                "O1,2026-01-01,East,10.5\n"
                "O2,2026-01-02,West,20.0\n"
                "O3,2026-01-03,East,15.0\n",
                encoding="utf-8",
            )

            probe_proc = self.run_cmd(
                [
                    sys.executable,
                    str(REFINE_PROBE),
                    "--workspace",
                    str(workspace),
                    "--dataset-id",
                    "duckdb.test.orders",
                    "--refine-id",
                    "gap-test",
                    "--data-csv",
                    str(csv_path),
                ]
            )
            self.assertEqual(probe_proc.returncode, 0, probe_proc.stdout + probe_proc.stderr)
            probe = json.loads((workspace / "runtime" / "metadata-refine" / "gap-test" / "data_probe.json").read_text(encoding="utf-8"))
            self.assertIn("order_id", probe["probe"]["candidate_key_fields"])
            self.assertIn("order_id", probe["probe"]["likely_grain"])
            amount = next(column for column in probe["probe"]["columns"] if column["name"] == "amount")
            self.assertEqual(amount["numeric_range"], {"min": 10.5, "max": 20.0})
            order_date = next(column for column in probe["probe"]["columns"] if column["name"] == "order_date")
            self.assertEqual(order_date["date_range"], {"min": "2026-01-01", "max": "2026-01-03"})

            workflow_proc = self.run_cmd(
                [
                    sys.executable,
                    str(REFINE_RESOLVE_GAPS),
                    "--workspace",
                    str(workspace),
                    "--dataset-id",
                    "duckdb.test.orders",
                    "--refine-id",
                    "gap-workflow",
                    "--data-csv",
                    str(csv_path),
                ]
            )
            self.assertEqual(workflow_proc.returncode, 0, workflow_proc.stdout + workflow_proc.stderr)
            payload = json.loads(workflow_proc.stdout)
            self.assertTrue(payload["success"])
            self.assertEqual(payload["suggestion_status"], "candidate_requires_human_review")
            reference = (workspace / "runtime" / "metadata-refine" / "gap-workflow" / "metadata_update_reference.md").read_text(encoding="utf-8")
            self.assertIn("Candidate Metadata Maintenance Suggestions", reference)
            self.assertIn("candidate_requires_human_review", reference)
            self.assertIn("numeric_range=10.5..20.0", reference)
            self.assertIn("date_range=2026-01-01..2026-01-03", reference)

    def test_mysql_clickhouse_sync_registry_status_and_report(self) -> None:
        for connector in ("mysql", "clickhouse"):
            with tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                write_sql_dataset(workspace, connector)
                validate = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "validate"])
                self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

                dry_run = self.run_cmd(
                    [
                        sys.executable,
                        str(METADATA),
                        "--workspace",
                        str(workspace),
                        "sync-registry",
                        "--dataset-id",
                        f"{connector}.test.orders",
                        "--dry-run",
                    ]
                )
                self.assertEqual(dry_run.returncode, 0, dry_run.stdout + dry_run.stderr)
                preview = json.loads(dry_run.stdout)
                self.assertTrue(preview["success"])

                sync = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "sync-registry", "--dataset-id", f"{connector}.test.orders"])
                self.assertEqual(sync.returncode, 0, sync.stdout + sync.stderr)
                status = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "status", "--dataset-id", f"{connector}.test.orders"])
                self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
                status_payload = json.loads(status.stdout)["results"][0]
                self.assertEqual(status_payload["source_backend"], connector)
                self.assertTrue(status_payload["export_ready"])

                report = self.run_cmd([sys.executable, str(METADATA_REPORTER), "--workspace", str(workspace), "--connector", connector, "--dataset-id", f"{connector}.test.orders"])
                self.assertEqual(report.returncode, 0, report.stdout + report.stderr)
                reports = list((workspace / "metadata" / "sync" / connector / "reports").glob(f"*{connector}.test.orders_sync_report.md"))
                self.assertEqual(len(reports), 1)
                content = reports[0].read_text(encoding="utf-8")
                self.assertIn("connection_ref", content)
                self.assertNotIn("Tableau 参数边界", content)
                self.assertNotIn("样本值来自只读采样", content)

    def test_sql_export_common_uses_whitelist_parameters_and_summary(self) -> None:
        module = load_script(SQL_EXPORT_COMMON, "sql_export_common_test")

        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[tuple[str, list[str]]] = []

            def query(self, sql: str, params: list[str]):
                self.calls.append((sql, params))
                return ["region", "total_amount"], [("East", 12)]

        fake_client = FakeClient()
        old_ensure = module.ensure_valid_source
        module.ensure_valid_source = lambda source_id, connector: (
            {
                "key": source_id,
                "source_backend": connector,
                "status": "active",
                "display_name": "Orders",
                "fields": ["region", "amount", "order_date"],
                connector: {"database": "analytics", "table": "orders", "connection_ref": "MYSQL_CONNECTION_JSON"},
            },
            {
                "fields": ["region", "amount", "order_date"],
                "dimensions": [{"name": "region"}, {"name": "order_date"}],
                "measures": [{"name": "amount"}],
                "filters": [{"key": "region"}, {"key": "order_date"}],
            },
            {"database": "analytics", "table": "orders", "connection_ref": "MYSQL_CONNECTION_JSON"},
        )
        try:
            with tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                payload = module.run_export(
                    workspace=workspace,
                    connector="mysql",
                    source_id="mysql.test.orders",
                    session_id="session-1",
                    output_name="orders.csv",
                    selected_fields=[],
                    filters=[module.parse_filter("region=East")],
                    date_ranges=[module.parse_date_range("order_date:2026-01-01:2026-01-31")],
                    group_by=["region"],
                    aggregates=[module.parse_aggregate("amount:sum:total_amount")],
                    order_by=[module.parse_order("total_amount:desc")],
                    limit=5,
                    client=fake_client,
                    placeholder="%s",
                )
                self.assertTrue(Path(payload["output_file"]).exists())
                summary = json.loads(Path(payload["latest_summary_file"]).read_text(encoding="utf-8"))
        finally:
            module.ensure_valid_source = old_ensure

        sql, params = fake_client.calls[0]
        self.assertIn("WHERE `region` = %s", sql)
        self.assertIn("CAST(`order_date` AS DATE) BETWEEN %s AND %s", sql)
        self.assertEqual(params, ["East", "2026-01-01", "2026-01-31"])
        self.assertEqual(summary["source_backend"], "mysql")
        self.assertEqual(summary["connection_ref"], "MYSQL_CONNECTION_JSON")
        self.assertNotIn("password", json.dumps(summary).lower())
        self.assertEqual(module.safe_ref("mysql://user:password@example/db"), "[redacted]")

        with self.assertRaises(ValueError):
            module.validate_fields(["not_registered"], {"region"})
        with self.assertRaises(ValueError):
            module.resolve_output_file(Path("/tmp/workspace"), "session-1", "../escape.csv")

    def test_registry_metrics_use_canonical_ids_while_export_keeps_source_fields(self) -> None:
        sync_module = load_script(SYNC_REGISTRY, "sync_registry_canonical_metrics_test")
        dataset = {
            "version": 1,
            "id": "clickhouse.default.vm_flight_history",
            "display_name": "Flight History",
            "source": {
                "connector": "clickhouse",
                "object": "default.vm_flight_history",
                "clickhouse": {"database": "default", "table": "vm_flight_history", "connection_ref": "CLICKHOUSE_CONNECTION_JSON"},
            },
            "business": {"grain": ["flight_id"], "time_fields": [], "suitable_for": [], "not_suitable_for": [], "sample_questions": []},
            "maintenance": {"owner": "test", "pending_questions": []},
            "fields": [
                {"name": "am_income_field", "display_name": "AM Income Field", "physical_name": "amIncome", "role": "metric_source", "type": "number", "business_definition": definition("income field")},
                {"name": "flight_id", "display_name": "Flight ID", "physical_name": "flightId", "role": "identifier", "type": "string", "business_definition": definition("flight id")},
            ],
            "metrics": [
                {
                    "name": "am_income",
                    "display_name": "AM Income",
                    "expression": "SUM(amIncome)",
                    "aggregation": "sum",
                    "unit": "CNY",
                    "business_definition": definition("AM income metric"),
                }
            ],
        }

        entry, spec = sync_module.build_entry_and_spec(dataset)

        self.assertEqual(entry["semantics"]["available_metrics"], ["am_income"])
        self.assertIn("amIncome", entry["fields"])
        self.assertIn("amIncome", spec["fields"])
        self.assertNotIn("source_field", spec["metrics"][0])
        self.assertEqual(spec["metrics"][0]["definition_status"], "confirmed")
        self.assertEqual(spec["metrics"][0]["semantic_ref_status"], "local_confirmed")
        self.assertEqual(spec["metrics"][0]["semantic_ref_label"], "本地确认口径")
        self.assertEqual(spec["dimensions"][0]["semantic_ref_status"], "local_confirmed")

        source_context = load_script(SOURCE_CONTEXT, "source_context_canonical_metrics_test")
        old_loader = source_context.load_spec_for_entry
        source_context.load_spec_for_entry = lambda src: spec
        try:
            context = source_context.build_source_context(entry)
        finally:
            source_context.load_spec_for_entry = old_loader

        self.assertEqual(context["unresolved_metrics"], [])
        self.assertEqual(context["metrics"][0]["metric_id"], "am_income")
        self.assertNotIn("source_field", context["metrics"][0])
        self.assertEqual(context["metrics"][0]["expression"], "SUM(amIncome)")
        self.assertEqual(context["metrics"][0]["aggregation"], "sum")
        self.assertEqual(context["metrics"][0]["unit"], "CNY")
        self.assertEqual(context["metrics"][0]["definition_status"], "confirmed")
        self.assertEqual(context["metrics"][0]["semantic_ref_status"], "local_confirmed")
        self.assertEqual(context["metrics"][0]["semantic_ref_label"], "本地确认口径")

    def test_mysql_clickhouse_export_help_and_audit_sql_summary(self) -> None:
        for path in [MYSQL_EXPORTER, MYSQL_EXPORT_WRAPPER, CLICKHOUSE_EXPORTER, CLICKHOUSE_EXPORT_WRAPPER]:
            proc = self.run_cmd([sys.executable, str(path), "--help"], cwd=REPO)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("export", proc.stdout.lower())

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            job = workspace / "jobs" / "session-1"
            data_file = job / "data" / "orders.csv"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("region,total\nEast,12\n", encoding="utf-8")
            summary = job / "mysql_export_summary.json"
            summary.write_text(
                json.dumps(
                    {
                        "source_backend": "mysql",
                        "source_id": "mysql.test.orders",
                        "display_name": "Orders",
                        "database": "analytics",
                        "object_name": "orders",
                        "connection_ref": "MYSQL_CONNECTION_JSON",
                        "output_file": "jobs/session-1/data/orders.csv",
                        "row_count": 1,
                        "selected_fields": ["region", "total"],
                        "exported_at": "2026-05-12T00:00:00+08:00",
                    }
                ),
                encoding="utf-8",
            )
            env = {**os.environ, "ANALYST_WORKSPACE_DIR": str(workspace)}
            log_proc = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "scripts" / "log_acquisition.py"),
                    "--session-id",
                    "session-1",
                    "--from-sql-summary",
                    str(summary),
                    "--reason",
                    "test",
                ],
                cwd=REPO,
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(log_proc.returncode, 0, log_proc.stdout + log_proc.stderr)
            event_id = json.loads(log_proc.stdout)["event_id"]
            index_proc = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "scripts" / "update_artifact_index.py"),
                    "--session-id",
                    "session-1",
                    "--from-sql-summary",
                    str(summary),
                    "--event-id",
                    event_id,
                ],
                cwd=REPO,
                text=True,
                capture_output=True,
                env=env,
            )
            self.assertEqual(index_proc.returncode, 0, index_proc.stdout + index_proc.stderr)
            index = json.loads((workspace / "jobs" / "session-1" / ".meta" / "artifact_index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["items"][0]["source_backend"], "mysql")

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
                        "physical_name": "period_key",
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
        self.assertIn("语义引用状态", report)
        self.assertIn("本地确认口径", report)
        self.assertIn("本地草稿口径", report)
        self.assertIn("映射覆盖引用", report)
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
            self.assertIn("语义引用状态", content)
            self.assertIn("本地确认口径", content)
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

    def test_metadata_read_returns_dataset_facts_without_registry_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)

            proc = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "read", "--dataset-id", "test.dataset"])

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            result = payload["results"][0]
            self.assertEqual(result["dataset_id"], "test.dataset")
            self.assertTrue(result["status"]["metadata_yaml"])
            self.assertFalse(result["status"]["runtime_registry"])
            self.assertEqual(result["registry"]["status"], "未注册")

    def test_metadata_read_missing_dataset_returns_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)

            proc = self.run_cmd([sys.executable, str(METADATA), "--workspace", str(workspace), "read", "--dataset-id", "missing.dataset"])

            self.assertEqual(proc.returncode, 1)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["success"])
            self.assertEqual(payload["error_code"], "METADATA_READ_FAILED")

    def test_dataset_first_metadata_report_cli_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            (workspace / "jobs" / "session-1" / "profile").mkdir(parents=True)
            (workspace / "jobs" / "session-1" / "profile" / "profile.json").write_text(
                json.dumps({"sample_values": ["SHOULD_NOT_APPEAR"]}),
                encoding="utf-8",
            )

            proc = self.run_cmd([sys.executable, str(METADATA_REPORTER), "--workspace", str(workspace), "--dataset-id", "test.dataset"])

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report_path = workspace / "metadata" / "reports" / "test.dataset_metadata_report.md"
            self.assertTrue(report_path.exists())
            self.assertFalse((workspace / "metadata" / "reports" / "test.dataset_metadata_context.json").exists())
            content = report_path.read_text(encoding="utf-8")
            for heading in [
                "## 1. 元数据事实摘要",
                "## 2. 数据集信息",
                "## 3. 字段信息",
                "## 4. 指标信息",
                "## 5. 筛选、参数与取值信息",
                "## 7. 未维护项",
                "## 8. 运行与注册状态",
                "## 9. 报告生成信息",
            ]:
                self.assertIn(heading, content)
            self.assertIn("| 名称 | 系统标识 | 物理字段 | 角色 | 类型 | 业务定义 | 定义来源 | 状态 | 来源 |", content)
            self.assertIn("未维护", content)
            self.assertIn("未注册", content)
            self.assertIn("runtime/registry", content)
            self.assertNotIn("SHOULD_NOT_APPEAR", content)
            self.assertNotIn("metadata_context", content)
            self.assertNotIn("常见用途", content)
            self.assertNotIn("使用建议", content)

            report_path.write_text("old report", encoding="utf-8")
            rerun = self.run_cmd([sys.executable, str(METADATA_REPORTER), "--workspace", str(workspace), "--dataset-id", "test.dataset"])
            self.assertEqual(rerun.returncode, 0, rerun.stdout + rerun.stderr)
            self.assertNotEqual(report_path.read_text(encoding="utf-8"), "old report")

    def test_dataset_first_metadata_report_does_not_import_tableau_renderer(self) -> None:
        old_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name == "tableau_report":
                raise AssertionError("dataset-first report should not import tableau_report")
            return old_import(name, *args, **kwargs)

        try:
            builtins.__import__ = blocked_import
            module = load_script(METADATA_REPORTER, "generate_report_lazy_import_test")
        finally:
            builtins.__import__ = old_import
        self.assertTrue(callable(module.build_parser))

    def test_metadata_report_bootstrap_supports_installed_skill_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "metadata").mkdir()
            (workspace / "runtime").mkdir()
            script_dir = workspace / ".agents" / "skills" / "metadata-report" / "scripts"
            script_dir.mkdir(parents=True)
            (script_dir / "_bootstrap.py").write_text(METADATA_REPORT_BOOTSTRAP.read_text(encoding="utf-8"), encoding="utf-8")

            code = (
                "import json, sys;"
                f"sys.path.insert(0, {str(script_dir)!r});"
                "import _bootstrap;"
                "root=_bootstrap.bootstrap_workspace_path();"
                "print(json.dumps({'root': str(root), 'has_workspace': str(root) in sys.path, 'has_agents': str(root / '.agents') in sys.path}))"
            )
            env = {k: v for k, v in os.environ.items() if k != "ANALYST_WORKSPACE_DIR"}
            proc = subprocess.run([sys.executable, "-c", code], cwd=workspace, text=True, capture_output=True, env=env)

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(Path(payload["root"]).resolve(), workspace.resolve())
            self.assertTrue(payload["has_workspace"])
            self.assertTrue(payload["has_agents"])

    def test_dataset_first_metadata_report_uses_registry_ranges_not_sample_values(self) -> None:
        module = load_script(SQLITE_STORE, "sqlite_store_dataset_report_values_test")

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            dataset_path = workspace / "metadata" / "datasets" / "test.dataset.yaml"
            dataset = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
            dataset["fields"].extend(
                [
                    {
                        "name": "order_date",
                        "display_name": "order_date",
                        "role": "time_dimension",
                        "type": "date",
                        "description": "order date",
                        "business_definition": definition("order date definition"),
                    },
                    {
                        "name": "region",
                        "display_name": "region",
                        "role": "dimension",
                        "type": "string",
                        "description": "region",
                        "business_definition": definition("region definition"),
                    },
                    {
                        "name": "order_code",
                        "display_name": "order_code",
                        "role": "identifier",
                        "type": "string",
                        "description": "order code",
                        "business_definition": definition("order code definition"),
                    },
                ]
            )
            dataset_path.write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")
            old_db_path = module._DB_PATH
            module._DB_PATH = workspace / "runtime" / "registry.db"
            try:
                module.save_entry(
                    {
                        "key": "test.dataset",
                        "source_id": "test.dataset",
                        "type": "duckdb_table",
                        "source_backend": "duckdb",
                        "status": "active",
                        "category": "test",
                        "display_name": "Test Dataset",
                    }
                )
                module.save_spec(
                    {
                        "entry_key": "test.dataset",
                        "display_name": "Test Dataset",
                        "filters": [
                            {
                                "key": "year",
                                "display_name": "year",
                                "apply_via": "sql_where",
                                "allowed_values": [2021, 2022],
                                "sample_values": ["SHOULD_NOT_APPEAR"],
                                "validation": {"min": 2020, "max": 2026},
                            },
                            {
                                "key": "order_date",
                                "display_name": "order_date",
                                "apply_via": "sql_where",
                                "allowed_values": ["2020-02-02"],
                                "validation": {"min_date": "2020-01-01", "max_date": "2026-12-31"},
                            },
                            {
                                "key": "region",
                                "display_name": "region",
                                "apply_via": "sql_where",
                                "validation": {"allowed_values": ["East", "West"]},
                            },
                            {
                                "key": "order_code",
                                "display_name": "order_code",
                                "apply_via": "sql_where",
                                "validation": {"values": ["ORD-001", "ORD-002"]},
                            },
                            {
                                "key": "order_code",
                                "display_name": "order_code",
                                "apply_via": "sql_where",
                                "validation": {"pattern": "^ORD-[0-9]+$", "example": "ORD-001"},
                            }
                        ],
                    }
                )
            finally:
                module._DB_PATH = old_db_path

            proc = self.run_cmd([sys.executable, str(METADATA_REPORTER), "--workspace", str(workspace), "--dataset-id", "test.dataset"])

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            content = (workspace / "metadata" / "reports" / "test.dataset_metadata_report.md").read_text(encoding="utf-8")
            self.assertIn("2020 至 2026", content)
            self.assertIn("2020-01-01 至 2026-12-31", content)
            self.assertIn("East、West", content)
            self.assertIn("ORD-001、ORD-002", content)
            self.assertNotIn("2021、2022", content)
            self.assertNotIn("2020-02-02", content)
            self.assertNotIn("SHOULD_NOT_APPEAR", content)
            self.assertNotIn("格式：", content)

    def test_dataset_first_metadata_report_output_dir_and_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=0)
            output_dir = workspace / "custom_reports"

            proc = self.run_cmd(
                [
                    sys.executable,
                    str(METADATA_REPORTER),
                    "--workspace",
                    str(workspace),
                    "--all",
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report_path = output_dir / "test.dataset_metadata_report.md"
            self.assertTrue(report_path.exists())
            self.assertIn("[OK] report ->", proc.stdout)

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

    def test_data_analytics_semantic_export_generates_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            output_dir = workspace / "semantic_package"

            proc = self.run_cmd(
                [
                    sys.executable,
                    str(DATA_ANALYTICS_SEMANTIC_EXPORTER),
                    "--workspace",
                    str(workspace),
                    "--area",
                    "Test Retail",
                    "--dataset-id",
                    "test.dataset",
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["success"])
            self.assertEqual(Path(payload["output_path"]).resolve(), output_dir.resolve())
            self.assertEqual(len(payload["files_written"]), 3)
            self.assertIn("suggested_user_context_entry", payload)
            self.assertIn("data_analytics_validation_prompt", payload)
            self.assertIn("Data Analytics semantic-layer", payload["data_analytics_validation_prompt"])
            self.assertIn("metadata/datasets/test.dataset.yaml", payload["suggested_user_context_entry"] + (output_dir / "references" / "semantic-layer.md").read_text(encoding="utf-8"))

            skill = (output_dir / "SKILL.md").read_text(encoding="utf-8")
            semantic = (output_dir / "references" / "semantic-layer.md").read_text(encoding="utf-8")
            inventory = (output_dir / "references" / "source-inventory.md").read_text(encoding="utf-8")
            self.assertIn("name: test-retail-semantic-layer", skill)
            for heading in [
                "## Key Metrics",
                "## Field Mapping",
                "## Standard Filters And Dimensions",
                "## Key Tables",
                "## Open Questions",
            ]:
                self.assertIn(heading, semantic)
            self.assertIn("metric_field_0", semantic)
            self.assertIn("本地确认口径", semantic)
            self.assertIn("runtime registry not registered", semantic)
            self.assertIn("# Source Inventory", inventory)
            self.assertIn("## Source Priority", inventory)
            self.assertIn("Data Analytics user-context was not written automatically", inventory)

    def test_data_analytics_semantic_export_defaults_to_codex_home_and_redacts_sensitive_locators(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ra_project_") as tmp:
            workspace = Path(tmp)
            write_dataset(workspace, metric_field_count=1, metric_count=1)
            dataset_path = workspace / "metadata" / "datasets" / "test.dataset.yaml"
            dataset = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
            dataset["source"]["object"] = "mysql://user:password@example/db?token=abc123&api_key=sk_live"
            dataset_path.write_text(yaml.safe_dump(dataset, allow_unicode=True), encoding="utf-8")

            codex_home = workspace / "codex-home"
            env = os.environ.copy()
            env["CODEX_HOME"] = str(codex_home)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(DATA_ANALYTICS_SEMANTIC_EXPORTER),
                    "--workspace",
                    str(workspace),
                    "--area",
                    "Sensitive Area",
                    "--dataset-id",
                    "test.dataset",
                ],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            output_path = Path(payload["output_path"]).resolve()
            self.assertEqual(output_path.parent, (codex_home / "skills").resolve())
            self.assertEqual(output_path.name, "sensitive-area-semantic-layer")
            self.assertFalse((codex_home / "state" / "plugins" / "data-analytics" / "user-context.md").exists())

            generated_text = proc.stdout + "\n".join(path.read_text(encoding="utf-8") for path in output_path.rglob("*.md"))
            self.assertIn("[redacted-sensitive-locator]", generated_text)
            for secret_fragment in ("mysql://user", "password@example", "abc123", "sk_live"):
                self.assertNotIn(secret_fragment, generated_text)

    def test_data_analytics_semantic_export_auto_discovery_failure_is_json(self) -> None:
        module = load_script(DATA_ANALYTICS_SEMANTIC_EXPORTER, "data_analytics_semantic_export_error_test")
        old_argv = sys.argv
        old_finder = module._find_workspace
        module._find_workspace = lambda start: (_ for _ in ()).throw(module.ExportError("workspace unavailable"))
        stdout = io.StringIO()
        try:
            sys.argv = [str(DATA_ANALYTICS_SEMANTIC_EXPORTER), "--area", "Test Retail", "--dataset-id", "test.dataset"]
            with contextlib.redirect_stdout(stdout):
                exit_code = module.main()
        finally:
            sys.argv = old_argv
            module._find_workspace = old_finder

        self.assertEqual(exit_code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error_code"], "SEMANTIC_EXPORT_INPUT_INVALID")
        self.assertIn("workspace unavailable", payload["error"])


if __name__ == "__main__":
    unittest.main()
