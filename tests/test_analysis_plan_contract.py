import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VALIDATE_PLAN = REPO / "skills" / "analysis-plan" / "scripts" / "validate_plan.py"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from runtime import job_manifest


PLAN_TEXT = """# 分析计划

## 需求解析
内容。

## 参数确认
内容。

## 数据源定位
内容。

## 数据源元数据
内容。

## 分析框架
- **selected_framework_id**: `benchmark_radar`
- **framework_selection_reason**: 用户需要横向对标。
- **selected_analysis_mode**: `benchmark`
- **analysis_mode_selection_reason**: 目标是比较差距。
- **selected_delivery_mode**: `structured_report`
- **delivery_mode_selection_reason**: 需要正式结构化报告。
- **selected_report_template**: `competitor_compare`
- **template_selection_reason**: 对标报告最适合差距表达。

## 业务假设
### 假设 1
### 假设 2
### 假设 3

## 异常判定标准
内容。

## 下钻路径
内容。

## 分析目标
内容。

## 预期输出
内容。
"""


class AnalysisPlanContractTests(unittest.TestCase):
    def test_validate_plan_extracts_decision_and_updates_manifest(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO / "jobs") as tmp:
            job_dir = Path(tmp)
            meta = job_dir / ".meta"
            meta.mkdir()
            plan = meta / "analysis_plan.md"
            plan.write_text(PLAN_TEXT, encoding="utf-8")
            job_manifest.create_manifest(job_dir, job_id=job_dir.name, title="对标分析")

            proc = subprocess.run(
                [sys.executable, str(VALIDATE_PLAN), "--plan-file", str(plan), "--update-manifest"],
                cwd=REPO,
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["success"])
            self.assertTrue(payload["manifest_updated"])
            self.assertEqual(payload["decision"]["selected_analysis_mode"], "benchmark")

            manifest = job_manifest.load_manifest(job_dir)
            self.assertEqual(manifest["planning"]["selected_analysis_mode"], "benchmark")
            self.assertEqual(manifest["planning"]["selected_delivery_mode"], "structured_report")
            self.assertEqual(manifest["planning"]["selected_report_template"], "competitor_compare")
            plan_artifact = next(item for item in manifest["artifacts"] if item["id"] == "analysis_plan")
            self.assertEqual(plan_artifact["role"], "supporting_evidence")
            self.assertTrue(plan_artifact["internal_only"])

    def test_schema_docs_mark_legacy_operator_schema_and_add_decision_schema(self) -> None:
        legacy = json.loads((REPO / "schemas" / "analysis_plan.schema.json").read_text(encoding="utf-8"))
        decision = json.loads((REPO / "schemas" / "analysis_plan_decision.schema.json").read_text(encoding="utf-8"))

        self.assertIn("Legacy JSON operator plan", legacy["description"])
        self.assertIn("selected_analysis_mode", decision["required"])
        self.assertIn("competitor_compare", decision["properties"]["selected_report_template"]["enum"])
        self.assertNotIn("technical_deepdive", decision["properties"]["selected_report_template"]["enum"])


if __name__ == "__main__":
    unittest.main()
