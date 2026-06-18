import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "finalize_job_archive.py"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from runtime import job_manifest


class FinalizeJobArchiveTests(unittest.TestCase):
    def create_job(self, root: Path, *, status: str) -> Path:
        job_manifest.create_manifest(root, job_id=root.name, title="归档测试")
        manifest = job_manifest.load_manifest(root)
        manifest["job"]["status"] = status
        job_manifest.save_manifest(root, manifest)
        (root / "profile").mkdir()
        (root / "profile" / "profile.json").write_text("{}", encoding="utf-8")
        (root / "报告_测试.md").write_text("# 报告\n", encoding="utf-8")
        job_manifest.register_artifact(
            root,
            {
                "id": "profile_json",
                "role": "derived_internal",
                "kind": "json",
                "display_name": "画像明细",
                "path": "profile/profile.json",
                "producer": "data-profile",
                "user_visible": False,
                "internal_only": True,
                "safe_to_archive": True,
                "safe_to_delete": False,
            },
        )
        job_manifest.register_artifact(
            root,
            {
                "id": "report_main",
                "role": "user_deliverable",
                "kind": "markdown",
                "display_name": "测试报告",
                "path": "报告_测试.md",
                "producer": "report",
                "user_visible": True,
                "internal_only": False,
                "safe_to_archive": False,
                "safe_to_delete": False,
            },
        )
        return root

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=REPO, text=True, capture_output=True)

    def test_active_job_has_no_archive_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = self.create_job(Path(tmp), status="running")

            proc = self.run_script("--job-dir", str(job_dir))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["can_apply"])
            self.assertEqual(payload["candidate_count"], 0)
            self.assertTrue((job_dir / "profile" / "profile.json").exists())

    def test_delivered_dry_run_does_not_move_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = self.create_job(Path(tmp), status="delivered")

            proc = self.run_script("--job-dir", str(job_dir))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["can_apply"])
            self.assertEqual(payload["candidate_count"], 1)
            self.assertTrue((job_dir / "profile" / "profile.json").exists())
            self.assertFalse((job_dir / ".archive").exists())

    def test_apply_requires_confirmation_and_updates_recovery_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = self.create_job(Path(tmp), status="delivered")

            blocked = self.run_script("--job-dir", str(job_dir), "--apply")
            self.assertNotEqual(blocked.returncode, 0)
            self.assertTrue((job_dir / "profile" / "profile.json").exists())

            proc = self.run_script("--job-dir", str(job_dir), "--apply", "--confirm-delivered")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["moved_count"], 1)
            self.assertFalse((job_dir / "profile" / "profile.json").exists())
            self.assertTrue((job_dir / ".archive" / "internal" / "profile" / "profile.json").exists())
            manifest = job_manifest.load_manifest(job_dir)
            self.assertEqual(manifest["job"]["status"], "archived")
            artifact = next(item for item in manifest["artifacts"] if item["id"] == "profile_json")
            self.assertEqual(artifact["status"], "archived")
            self.assertEqual(artifact["archive"]["original_path"], "profile/profile.json")
            self.assertEqual(artifact["path"], ".archive/internal/profile/profile.json")


if __name__ == "__main__":
    unittest.main()
