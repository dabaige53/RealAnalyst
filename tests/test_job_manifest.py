from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
JOB_MANIFEST = REPO / "runtime" / "job_manifest.py"


class JobManifestTests(unittest.TestCase):
    def run_cmd(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, cwd=REPO, text=True, capture_output=True)

    def test_create_register_and_filter_user_visible_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "jobs" / "job_001"
            init_proc = self.run_cmd(
                [
                    sys.executable,
                    str(JOB_MANIFEST),
                    "init",
                    "--job-dir",
                    str(job_dir),
                    "--job-id",
                    "job_001",
                    "--title",
                    "经营分析",
                ]
            )
            self.assertEqual(init_proc.returncode, 0, init_proc.stderr)
            init_payload = json.loads(init_proc.stdout)
            self.assertTrue(init_payload["success"])
            self.assertTrue((job_dir / "job_manifest.json").exists())

            report = {
                "id": "report_main",
                "role": "user_deliverable",
                "kind": "report",
                "display_name": "经营分析报告",
                "path": "deliverables/report.md",
                "producer": "report",
            }
            profile = {
                "id": "profile_json",
                "role": "derived_internal",
                "kind": "json",
                "display_name": "数据画像",
                "path": "profile/profile.json",
                "producer": "data-profile",
            }
            for artifact in (report, profile):
                proc = self.run_cmd(
                    [
                        sys.executable,
                        str(JOB_MANIFEST),
                        "register-artifact",
                        "--job-dir",
                        str(job_dir),
                        "--artifact-json",
                        json.dumps(artifact, ensure_ascii=False),
                    ]
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertTrue(json.loads(proc.stdout)["success"])

            summary_proc = self.run_cmd([sys.executable, str(JOB_MANIFEST), "user-summary", "--job-dir", str(job_dir)])
            self.assertEqual(summary_proc.returncode, 0, summary_proc.stderr)
            summary = json.loads(summary_proc.stdout)
            self.assertEqual([item["id"] for item in summary["deliverables"]], ["report_main"])
            self.assertEqual(summary["user_surface"]["primary_deliverable_id"], "report_main")

            manifest = json.loads((job_dir / "job_manifest.json").read_text(encoding="utf-8"))
            internal = next(item for item in manifest["artifacts"] if item["id"] == "profile_json")
            self.assertTrue(internal["internal_only"])
            self.assertFalse(internal["user_visible"])

    def test_rejects_artifact_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "job_001"
            init_proc = self.run_cmd([sys.executable, str(JOB_MANIFEST), "init", "--job-dir", str(job_dir)])
            self.assertEqual(init_proc.returncode, 0, init_proc.stderr)

            artifact = {
                "id": "bad",
                "role": "supporting_evidence",
                "kind": "json",
                "display_name": "bad",
                "path": "../outside.json",
                "producer": "test",
            }
            proc = self.run_cmd(
                [
                    sys.executable,
                    str(JOB_MANIFEST),
                    "register-artifact",
                    "--job-dir",
                    str(job_dir),
                    "--artifact-json",
                    json.dumps(artifact),
                ]
            )
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["success"])
            self.assertEqual(payload["error_code"], "JOB_MANIFEST_PATH_ESCAPE")

    def test_validate_reports_duplicate_artifact_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "job_001"
            init_proc = self.run_cmd([sys.executable, str(JOB_MANIFEST), "init", "--job-dir", str(job_dir)])
            self.assertEqual(init_proc.returncode, 0, init_proc.stderr)
            manifest_path = job_dir / "job_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifact = {
                "id": "dup",
                "role": "derived_internal",
                "kind": "json",
                "display_name": "duplicate",
                "path": "profile/a.json",
                "user_visible": False,
                "internal_only": True,
                "producer": "test",
                "created_at": manifest["job"]["created_at"],
                "status": "ready",
                "safe_to_archive": True,
                "safe_to_delete": False,
            }
            manifest["artifacts"] = [artifact, dict(artifact, path="profile/b.json")]
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            proc = self.run_cmd([sys.executable, str(JOB_MANIFEST), "validate", "--job-dir", str(job_dir)])
            self.assertNotEqual(proc.returncode, 0)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["success"])
            self.assertIn("duplicates dup", "\n".join(payload["errors"]))


if __name__ == "__main__":
    unittest.main()
