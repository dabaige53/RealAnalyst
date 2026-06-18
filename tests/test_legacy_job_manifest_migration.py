import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "legacy_job_manifest_migration.py"


class LegacyJobManifestMigrationTests(unittest.TestCase):
    def test_dry_run_emits_candidate_manifest_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp)
            (job_dir / ".meta").mkdir()
            (job_dir / "data").mkdir()
            (job_dir / "profile").mkdir()
            (job_dir / "报告_经营分析.md").write_text("# 报告\n", encoding="utf-8")
            (job_dir / "汇总_销售.csv").write_text("a,b\n1,2\n", encoding="utf-8")
            (job_dir / "data" / "raw.csv").write_text("a,b\n1,2\n", encoding="utf-8")
            (job_dir / "profile" / "profile.json").write_text("{}", encoding="utf-8")
            (job_dir / ".meta" / "artifact_index.json").write_text("{}", encoding="utf-8")
            (job_dir / "notes.tmp").write_text("unknown", encoding="utf-8")
            before = sorted(path.relative_to(job_dir).as_posix() for path in job_dir.rglob("*") if path.is_file())

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--job-dir", str(job_dir)],
                cwd=REPO,
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            after = sorted(path.relative_to(job_dir).as_posix() for path in job_dir.rglob("*") if path.is_file())
            self.assertEqual(before, after)
            self.assertFalse((job_dir / "job_manifest.json").exists())

            payload = json.loads(proc.stdout)
            manifest = payload["candidate_manifest"]
            self.assertTrue(payload["dry_run"])
            self.assertEqual(manifest["job"]["status"], "ready_for_review")

            by_path = {item["path"]: item for item in manifest["artifacts"]}
            self.assertEqual(by_path["报告_经营分析.md"]["role"], "user_deliverable")
            self.assertEqual(by_path["汇总_销售.csv"]["role"], "user_attachment")
            self.assertEqual(by_path["data/raw.csv"]["role"], "raw_input")
            self.assertEqual(by_path["profile/profile.json"]["role"], "derived_internal")
            self.assertEqual(by_path["notes.tmp"]["role"], "unknown_legacy")
            self.assertIn("## Unknown Legacy Items", payload["review_markdown"])


if __name__ == "__main__":
    unittest.main()
