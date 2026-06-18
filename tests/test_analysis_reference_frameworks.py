from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ANALYSIS_REFERENCE = REPO / "skills" / "analysis-reference" / "scripts" / "query_config.py"
REFERENCE_LOOKUP = REPO / "skills" / "reference-lookup" / "scripts" / "query_config.py"


def run_query(script: Path, *args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    return json.loads(proc.stdout)


class AnalysisReferenceFrameworkTests(unittest.TestCase):
    def test_analysis_reference_framework_aliases_return_real_config(self) -> None:
        cases = {
            "mece": "mece_issue_tree",
            "waterfall": "waterfall_attribution",
            "osm": "gsm_metric_planning",
            "radar": "benchmark_radar",
            "funnel": "funnel_conversion",
        }

        for alias, expected_id in cases.items():
            with self.subTest(alias=alias):
                result = run_query(ANALYSIS_REFERENCE, "--framework", alias)

                self.assertTrue(result["found"])
                self.assertEqual(result["framework"]["id"], expected_id)
                self.assertTrue(result["framework"]["logic_path"])
                self.assertIn("goal_template", result["framework"])
                self.assertIn("dimension_type_hints", result["framework"])
                self.assertIn("evidence_requirements", result["framework"])
                self.assertIn("recommended_templates", result["framework"])

    def test_analysis_reference_framework_miss_lists_available_frameworks(self) -> None:
        result = run_query(ANALYSIS_REFERENCE, "--framework", "not-a-framework")

        self.assertFalse(result["found"])
        self.assertGreaterEqual(len(result["available_frameworks"]), 5)
        self.assertIn("mece_issue_tree", {row["id"] for row in result["available_frameworks"]})

    def test_legacy_reference_lookup_uses_same_framework_registry(self) -> None:
        result = run_query(REFERENCE_LOOKUP, "--framework", "waterfall")

        self.assertTrue(result["found"])
        self.assertEqual(result["framework"]["id"], "waterfall_attribution")


if __name__ == "__main__":
    unittest.main()
