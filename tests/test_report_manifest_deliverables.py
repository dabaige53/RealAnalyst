from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
REPORT_SCRIPT = REPO / "skills" / "report" / "scripts" / "append_report_update.py"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from runtime import job_manifest


def _load_report_module():
    spec = importlib.util.spec_from_file_location("append_report_update", REPORT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load append_report_update.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReportManifestDeliverablesTests(unittest.TestCase):
    def test_refresh_file_list_uses_manifest_visible_artifacts_only(self) -> None:
        module = _load_report_module()
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            module.WORKSPACE_DIR = workspace
            session_id = "job_001"
            job_dir = workspace / "jobs" / session_id
            report_path = job_dir / "报告_经营分析.md"
            report_path.parent.mkdir(parents=True)
            report_path.write_text("# 经营分析\n\n正文。\n", encoding="utf-8")
            (job_dir / "data").mkdir()
            (job_dir / "data" / "raw.csv").write_text("a\n1\n", encoding="utf-8")
            (job_dir / "profile").mkdir()
            (job_dir / "profile" / "profile.json").write_text("{}", encoding="utf-8")

            job_manifest.create_manifest(job_dir, job_id=session_id, title="经营分析")
            job_manifest.register_artifact(
                job_dir,
                {
                    "id": "attachment_summary",
                    "role": "user_attachment",
                    "kind": "csv",
                    "display_name": "经营汇总表",
                    "path": "汇总_经营分析.csv",
                    "producer": "report",
                },
            )
            job_manifest.register_artifact(
                job_dir,
                {
                    "id": "profile_json",
                    "role": "derived_internal",
                    "kind": "json",
                    "display_name": "数据画像",
                    "path": "profile/profile.json",
                    "producer": "data-profile",
                },
            )

            with patch.object(
                sys,
                "argv",
                [
                    str(REPORT_SCRIPT),
                    "--session-id",
                    session_id,
                    "--report-path",
                    str(report_path),
                    "--refresh-file-list",
                ],
            ):
                self.assertEqual(module.main(), 0)

            updated = report_path.read_text(encoding="utf-8")
            self.assertIn("### 用户可见交付物", updated)
            self.assertIn("经营汇总表", updated)
            self.assertIn("报告_经营分析", updated)
            self.assertNotIn("data/raw.csv", updated)
            self.assertNotIn("profile/profile.json", updated)

            manifest = job_manifest.load_manifest(job_dir)
            report = next(item for item in manifest["artifacts"] if item["id"] == "report_main")
            self.assertEqual(report["role"], "user_deliverable")
            self.assertTrue(report["user_visible"])

    def test_refresh_file_list_falls_back_without_manifest(self) -> None:
        module = _load_report_module()
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            module.WORKSPACE_DIR = workspace
            session_id = "job_legacy"
            job_dir = workspace / "jobs" / session_id
            report_path = job_dir / "报告_旧流程.md"
            report_path.parent.mkdir(parents=True)
            report_path.write_text("# 旧流程\n\n正文。\n", encoding="utf-8")
            (job_dir / "汇总_旧流程.csv").write_text("a\n1\n", encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    str(REPORT_SCRIPT),
                    "--session-id",
                    session_id,
                    "--report-path",
                    str(report_path),
                    "--refresh-file-list",
                ],
            ), patch("builtins.print") as mocked_print:
                self.assertEqual(module.main(), 0)

            payload = json.loads(mocked_print.call_args.args[0])
            self.assertIn("legacy_file_list_fallback", payload["warnings"])
            updated = report_path.read_text(encoding="utf-8")
            self.assertIn("### 分析产物(已附邮件)", updated)
            self.assertIn("汇总_旧流程.csv", updated)


if __name__ == "__main__":
    unittest.main()
