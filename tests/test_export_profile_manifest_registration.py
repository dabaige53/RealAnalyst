import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UPDATE_INDEX = REPO / "scripts" / "update_artifact_index.py"
RENDER_REPLY = REPO / "skills" / "analysis-run" / "scripts" / "render_user_reply.py"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from runtime import job_manifest


class ExportProfileManifestRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_id = f"test_manifest_sync_{id(self)}"
        self.job_dir = REPO / "jobs" / self.session_id
        self.job_dir.mkdir(parents=True, exist_ok=True)
        (self.job_dir / "data").mkdir(exist_ok=True)
        (self.job_dir / "profile").mkdir(exist_ok=True)
        (self.job_dir / "data" / "raw.csv").write_text("a,b\n1,x\n", encoding="utf-8")
        (self.job_dir / "profile" / "manifest.json").write_text("{}", encoding="utf-8")
        (self.job_dir / "profile" / "profile.json").write_text("{}", encoding="utf-8")
        (self.job_dir / "汇总_销售.csv").write_text("月份,订单量\n一月,10\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.job_dir, ignore_errors=True)

    def run_update(self, *items: dict[str, object]) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(UPDATE_INDEX), "--session-id", self.session_id]
        for item in items:
            command += ["--item", json.dumps(item, ensure_ascii=False)]
        return subprocess.run(command, cwd=REPO, text=True, capture_output=True)

    def test_export_and_profile_items_sync_to_job_manifest_roles(self) -> None:
        proc = self.run_update(
            {
                "path": f"jobs/{self.session_id}/data/raw.csv",
                "kind": "raw_data",
                "role": "archive",
                "source_backend": "duckdb",
                "display_name": "订单明细原始导出",
            },
            {
                "path": f"jobs/{self.session_id}/profile/manifest.json",
                "kind": "profile_manifest",
                "role": "system",
            },
            {
                "path": f"jobs/{self.session_id}/profile/profile.json",
                "kind": "profile",
                "role": "system",
            },
            {
                "path": f"jobs/{self.session_id}/汇总_销售.csv",
                "kind": "analysis_table",
                "role": "user",
                "display_name": "销售汇总表",
            },
        )

        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        manifest = job_manifest.load_manifest(self.job_dir)

        by_path = {item["path"]: item for item in manifest["artifacts"]}
        self.assertEqual(by_path["data/raw.csv"]["role"], "raw_input")
        self.assertTrue(by_path["data/raw.csv"]["internal_only"])
        self.assertFalse(by_path["data/raw.csv"]["user_visible"])

        self.assertEqual(by_path["profile/manifest.json"]["role"], "derived_internal")
        self.assertEqual(by_path["profile/profile.json"]["role"], "derived_internal")
        self.assertTrue(by_path["profile/manifest.json"]["internal_only"])
        self.assertTrue(by_path["profile/profile.json"]["internal_only"])

        self.assertEqual(by_path["汇总_销售.csv"]["role"], "user_attachment")
        self.assertTrue(by_path["汇总_销售.csv"]["user_visible"])
        visible_names = [item["display_name"] for item in job_manifest.user_visible_artifacts(self.job_dir)]
        self.assertEqual(visible_names, ["销售汇总表"])

    def test_rendered_user_reply_hides_profile_paths_after_sync(self) -> None:
        proc = self.run_update(
            {
                "path": f"jobs/{self.session_id}/profile/manifest.json",
                "kind": "profile_manifest",
                "role": "system",
            },
            {
                "path": f"jobs/{self.session_id}/汇总_销售.csv",
                "kind": "analysis_table",
                "role": "user",
                "display_name": "销售汇总表",
            },
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

        reply_proc = subprocess.run(
            [sys.executable, str(RENDER_REPLY), "--job-dir", str(self.job_dir), "--json"],
            cwd=REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(reply_proc.returncode, 0, reply_proc.stderr + reply_proc.stdout)
        payload = json.loads(reply_proc.stdout)
        self.assertNotIn("profile/manifest.json", payload["reply"])
        self.assertIn("销售汇总表", payload["reply"])

    def test_profile_manifest_schema_is_not_tableau_only(self) -> None:
        schema = json.loads((REPO / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
        self.assertNotIn("view_luid", schema["required"])
        self.assertNotIn("api_url", schema["required"])
        self.assertIn("profile_summary", schema["properties"])
        self.assertIn("physical_type", schema["properties"]["schema"]["properties"]["columns"]["items"]["properties"])


if __name__ == "__main__":
    unittest.main()
