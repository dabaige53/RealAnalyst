from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
INIT_SCRIPT = REPO / "skills" / "analysis-run" / "scripts" / "init_or_resume_job.py"
RENDER_SCRIPT = REPO / "skills" / "analysis-run" / "scripts" / "render_user_reply.py"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from runtime import job_manifest


def _load_init_module():
    spec = importlib.util.spec_from_file_location("analysis_run_init_or_resume_job", INIT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load init_or_resume_job.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AnalysisRunManifestIntegrationTests(unittest.TestCase):
    def test_init_creates_manifest_and_registers_legacy_artifact_index(self) -> None:
        module = _load_init_module()
        with tempfile.TemporaryDirectory() as tmp:
            jobs_dir = Path(tmp) / "jobs"
            module.JOBS_DIR = jobs_dir
            module.STATE_DIR = jobs_dir / "_state"
            module.STATE_PATH = module.STATE_DIR / "session_map.json"

            with patch.object(sys, "argv", [str(INIT_SCRIPT), "--key", "chat:abc", "--prefix", "test"]):
                self.assertEqual(module.main(), 0)

            state = json.loads((jobs_dir / "_state" / "session_map.json").read_text(encoding="utf-8"))
            session_id = state["active"]["chat:abc"]["job_id"]
            manifest = job_manifest.load_manifest(jobs_dir / session_id)

            self.assertEqual(manifest["job"]["id"], session_id)
            legacy = next(item for item in manifest["artifacts"] if item["id"] == "legacy_artifact_index")
            self.assertEqual(legacy["role"], "legacy")
            self.assertFalse(legacy["user_visible"])
            self.assertTrue(legacy["internal_only"])
            self.assertTrue((jobs_dir / session_id / ".meta" / "artifact_index.json").exists())

    def test_resume_old_job_backfills_manifest_without_replacing_legacy_index(self) -> None:
        module = _load_init_module()
        with tempfile.TemporaryDirectory() as tmp:
            jobs_dir = Path(tmp) / "jobs"
            module.JOBS_DIR = jobs_dir
            module.STATE_DIR = jobs_dir / "_state"
            module.STATE_PATH = module.STATE_DIR / "session_map.json"
            old_job = jobs_dir / "existing_job"
            old_meta = old_job / ".meta"
            old_meta.mkdir(parents=True)
            legacy_payload = {"version": 1, "job_id": "existing_job", "items": [{"id": "old"}]}
            (old_meta / "artifact_index.json").write_text(json.dumps(legacy_payload), encoding="utf-8")
            module.STATE_DIR.mkdir(parents=True)
            module.STATE_PATH.write_text(
                json.dumps({"version": 1, "active": {"chat:abc": {"job_id": "existing_job"}}}),
                encoding="utf-8",
            )

            with patch.object(sys, "argv", [str(INIT_SCRIPT), "--key", "chat:abc"]):
                self.assertEqual(module.main(), 0)

            self.assertEqual(
                json.loads((old_meta / "artifact_index.json").read_text(encoding="utf-8")),
                legacy_payload,
            )
            manifest = job_manifest.load_manifest(old_job)
            self.assertEqual(manifest["job"]["id"], "existing_job")
            self.assertTrue(any(item["id"] == "legacy_artifact_index" for item in manifest["artifacts"]))

    def test_default_rendered_reply_hides_internal_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "job"
            job_manifest.create_manifest(job_dir, job_id="job", title="经营分析")
            job_manifest.register_artifact(
                job_dir,
                {
                    "id": "report_main",
                    "role": "user_deliverable",
                    "kind": "report",
                    "display_name": "经营分析报告",
                    "path": "reports/final_report.md",
                    "producer": "report",
                },
            )
            job_manifest.update_user_surface(
                job_dir,
                {
                    "summary": "分析完成，报告已更新。",
                    "verification_status": "passed",
                    "risks": ["样本期较短，趋势判断需要保守。"],
                    "next_actions": ["如需继续，可补充更长时间范围。"],
                },
            )

            proc = subprocess.run(
                [sys.executable, str(RENDER_SCRIPT), "--job-dir", str(job_dir)],
                cwd=REPO,
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("经营分析报告", proc.stdout)
            self.assertNotIn("reports/final_report.md", proc.stdout)
            self.assertNotIn("source_key", proc.stdout)
            self.assertNotIn("render_user_reply.py", proc.stdout)


if __name__ == "__main__":
    unittest.main()
