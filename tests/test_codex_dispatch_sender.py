from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture


class CodexDispatchSenderTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.instruction_path, _ = self.write_dispatch("codex")
        self.instruction = json.loads(self.instruction_path.read_text())
        self.instruction.update(
            status="in-progress", session_id=None,
            herdr_pane_id="worker-pane", herdr_terminal_id="terminal-worker-pane",
            plan_id="p-memory-plan", task_id="n2",
        )
        self.instruction_path.write_text(json.dumps(self.instruction))
        self.status_path = self.home / ".straw-boss/plans/memory-plan/status/n2.json"
        self.status_path.parent.mkdir(parents=True)
        self.original = '{"status":"awaiting-user-input","note":"Worker checkpoint."}\n'
        self.status_path.write_text(self.original)
        self.ledger_path = self.instruction_path.with_suffix(".messages.jsonl")
        self.original_ledger = '{"direction":"to-main","message_id":"previous-worker-message"}\n'
        self.ledger_path.write_text(self.original_ledger)
        self.fake_bin, self.capture = self.install_fake_herdr()
        self.env = {
            "PATH": f"{self.fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(self.capture),
            "HERDR_PANE_ID": "worker-pane",
            "HERDR_AGENT_KINDS": json.dumps({"worker-pane": "codex", "main-pane": "claude"}),
            "HERDR_SESSIONS": json.dumps({"worker-pane": "worker-thread", "main-pane": "main-session"}),
            "CODEX_THREAD_ID": "memory-thread",
        }

    def assert_no_delivery(self) -> None:
        calls = [json.loads(line) for line in self.capture.read_text().splitlines()] if self.capture.exists() else []
        self.assertFalse(any(call[:2] == ["agent", "prompt"] for call in calls))
        self.assertEqual(self.ledger_path.read_text(), self.original_ledger)

    def test_background_thread_preserves_status_through_both_addressing_routes(self) -> None:
        for address in (
            ["--instruction-path", str(self.instruction_path)],
            ["--plan", "memory-plan", "--task", "n2"],
        ):
            with self.subTest(address=address):
                self.status_path.write_text(self.original)
                result = self.run_script(
                    "report-task-status.py", *address, "--status", "failed",
                    "--note", "Memory consolidation finished.", extra_env=self.env,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("sender thread", result.stderr)
                self.assertEqual(self.status_path.read_text(), self.original)
                self.assert_no_delivery()

    def test_background_thread_cannot_send_or_record_a_message(self) -> None:
        result = self.run_script(
            "send-dispatch-message.py", "--instruction-path", str(self.instruction_path),
            "--to", "main", "--intent", "inform", "--message", "Memory consolidation finished.",
            extra_env=self.env,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("sender thread", result.stderr)
        self.assert_no_delivery()

    def test_missing_caller_or_live_thread_is_unverifiable(self) -> None:
        for overrides in ({"CODEX_THREAD_ID": ""}, {"HERDR_OMIT_AGENT_SESSION": "1"}):
            with self.subTest(overrides=overrides):
                result = self.run_script(
                    "report-task-status.py", "--instruction-path", str(self.instruction_path),
                    "--status", "done", "--note", "Work finished.",
                    extra_env={**self.env, **overrides},
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("sender thread", result.stderr)
                self.assertEqual(self.status_path.read_text(), self.original)
                self.assert_no_delivery()

    def test_worker_can_report_with_legacy_and_pinned_session_ids(self) -> None:
        for recorded_session in (None, "worker-thread"):
            with self.subTest(recorded_session=recorded_session):
                self.instruction["session_id"] = recorded_session
                self.instruction_path.write_text(json.dumps(self.instruction))
                result = self.run_script(
                    "report-task-status.py", "--instruction-path", str(self.instruction_path),
                    "--status", "done", "--note", "Work reviewed and verified.",
                    extra_env={**self.env, "CODEX_THREAD_ID": "worker-thread"},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(self.status_path.read_text())["status"], "done")
                self.assertIn("notified main agent", result.stdout)

    def test_main_can_cancel_without_impersonating_the_worker(self) -> None:
        result = self.run_script(
            "report-task-status.py", "--instruction-path", str(self.instruction_path),
            "--status", "cancelled", "--note", "Cancelled by the main agent.",
            extra_env={**self.env, "HERDR_PANE_ID": "main-pane", "CODEX_THREAD_ID": ""},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.status_path.read_text())["status"], "cancelled")
