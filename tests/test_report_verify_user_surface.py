import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = REPO / "skills" / "report-verify" / "scripts" / "verify.py"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from runtime import job_manifest


def load_verify_module():
    spec = importlib.util.spec_from_file_location("report_verify_test_module", VERIFY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ReportVerifyUserSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verify = load_verify_module()

    def write_inputs(self, job_dir: Path, report: str) -> tuple[Path, Path, Path]:
        csv_path = job_dir / "data.csv"
        analysis_path = job_dir / "analysis.json"
        report_path = job_dir / "报告_销售分析.md"
        csv_path.write_text("月份,订单量\n一月,10\n二月,12\n", encoding="utf-8")
        analysis_path.write_text(json.dumps({"findings": [], "statistics": {}}, ensure_ascii=False), encoding="utf-8")
        report_path.write_text(report, encoding="utf-8")
        return csv_path, analysis_path, report_path

    def base_report(self, extra: str = "") -> str:
        return (
            "# 销售分析报告\n\n"
            "## 数据来源\n"
            "- 示例销售数据\n\n"
            "## 结论\n"
            "当前样本用于验证报告门禁。\n\n"
            "## 口径说明（本次新增/临时）\n\n"
            "| 名称 | 业务含义 | 计算逻辑 | 来源 |\n"
            "| --- | --- | --- | --- |\n"
            "| 订单量 | 成交订单数量 | 汇总 | 示例销售数据 |\n\n"
            "## 输出文件清单\n\n"
            "### 用户可见交付物\n"
            "- 销售分析报告\n"
            f"{extra}"
        )

    def test_internal_path_leak_fails_normal_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp)
            csv_path, analysis_path, report_path = self.write_inputs(
                job_dir,
                self.base_report("- jobs/session-1/data/raw.csv\n"),
            )

            result = self.verify.verify_report(str(csv_path), str(analysis_path), str(report_path), str(job_dir))

            self.assertFalse(result["success"])
            verification = json.loads((job_dir / "verification.json").read_text(encoding="utf-8"))
            leak_check = next(item for item in verification["checks"] if item["check_type"] == "user_surface_leakage")
            self.assertEqual(leak_check["status"], "failed")
            self.assertEqual(leak_check["details"]["matches"][0]["type"], "job_path")

    def test_marked_technical_section_can_be_exempted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp)
            technical_block = (
                "\n<!-- RA:technical-details:start -->\n"
                "内部复核：jobs/session-1/data/raw.csv 由 scripts/export.py 生成。\n"
                "<!-- RA:technical-details:end -->\n"
            )
            csv_path, analysis_path, report_path = self.write_inputs(job_dir, self.base_report(technical_block))

            result = self.verify.verify_report(
                str(csv_path),
                str(analysis_path),
                str(report_path),
                str(job_dir),
                allow_technical_details=True,
            )

            self.assertTrue(result["success"])
            verification = json.loads((job_dir / "verification.json").read_text(encoding="utf-8"))
            leak_check = next(item for item in verification["checks"] if item["check_type"] == "user_surface_leakage")
            self.assertEqual(leak_check["status"], "passed")
            self.assertEqual(leak_check["details"]["allowed_technical_sections"], 1)

    def test_verification_status_updates_manifest_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp)
            job_manifest.create_manifest(job_dir, job_id="session-1", title="销售分析")
            csv_path, analysis_path, report_path = self.write_inputs(job_dir, self.base_report())

            result = self.verify.verify_report(str(csv_path), str(analysis_path), str(report_path), str(job_dir))

            self.assertTrue(result["success"])
            self.assertTrue(result["manifest_updated"])
            manifest = job_manifest.load_manifest(job_dir)
            self.assertEqual(manifest["user_surface"]["verification_status"], "passed")
            self.assertEqual(manifest["verification"]["status"], "passed")

    def test_verification_schema_matches_actual_check_types(self) -> None:
        schema = json.loads((REPO / "schemas" / "verification.schema.json").read_text(encoding="utf-8"))
        check_schema = schema["definitions"]["Check"]["properties"]
        self.assertIn("user_surface_leakage", check_schema["check_type"]["enum"])
        self.assertNotEqual(check_schema["check_id"]["pattern"], "^chk_[0-9]{3}$")
        self.assertIn("check_categories", schema["properties"])


if __name__ == "__main__":
    unittest.main()
