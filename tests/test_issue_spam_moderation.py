from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MODERATOR = REPO / "scripts" / "moderate_issue_spam.py"


def load_moderator():
    spec = importlib.util.spec_from_file_location("issue_spam_moderator_test", MODERATOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class IssueSpamModerationTests(unittest.TestCase):
    def test_detects_payment_address_with_flexible_spacing(self) -> None:
        module = load_moderator()

        self.assertTrue(module.contains_spam("Payment Address (SOL/RTC): abc"))
        self.assertTrue(module.contains_spam("payment   address: abc"))
        self.assertFalse(module.contains_spam("payment method address field"))

    def test_plans_comment_delete_for_spam_comment(self) -> None:
        module = load_moderator()
        payload = {"comment": {"body": "Payment Address: abc", "url": "https://api.github.com/repos/o/r/issues/comments/1"}}

        action = module.planned_action("issue_comment", payload)

        self.assertIsNotNone(action)
        self.assertEqual(action.target_type, "comment")

    def test_plans_issue_sanitization_for_spam_issue_body(self) -> None:
        module = load_moderator()
        payload = {"issue": {"body": "Payment Address: abc", "url": "https://api.github.com/repos/o/r/issues/1"}}

        action = module.planned_action("issues", payload)

        self.assertIsNotNone(action)
        self.assertEqual(action.target_type, "issue")

    def test_cli_dry_run_outputs_planned_action(self) -> None:
        payload = {"comment": {"body": "Payment Address: abc", "url": "https://api.github.com/repos/o/r/issues/comments/1"}}
        with tempfile.TemporaryDirectory() as tmpdir:
            event_path = Path(tmpdir) / "event.json"
            event_path.write_text(json.dumps(payload), encoding="utf-8")

            proc = subprocess.run(
                [sys.executable, str(MODERATOR), "--event-name", "issue_comment", "--event-path", str(event_path), "--dry-run"],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["action"], "planned")
        self.assertEqual(result["target_type"], "comment")


if __name__ == "__main__":
    unittest.main()
