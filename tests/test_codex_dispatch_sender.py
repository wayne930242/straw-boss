from __future__ import annotations

import json
import os
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture
from straw_boss.herdr.session import contract_prompt_line


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

    def test_other_thread_cannot_write_progress_but_the_worker_can(self) -> None:
        # A spawned subagent's shell carries its own thread id, like a background one.
        progress_path = self.instruction_path.with_name(
            self.instruction_path.name.removesuffix(".json") + ".progress.jsonl"
        )
        arguments = [
            "report-progress.py", "--instruction-path", str(self.instruction_path),
            "--note", "Waiting on my review.", "--waiting-on", "review",
        ]
        refused = self.run_script(*arguments, extra_env=self.env)
        self.assertNotEqual(refused.returncode, 0, refused.stdout)
        self.assertIn("sender thread", refused.stderr)
        self.assertFalse(progress_path.exists())

        accepted = self.run_script(
            *arguments, extra_env={**self.env, "CODEX_THREAD_ID": "worker-thread"}
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(progress_path.read_text())["waiting_on"], "review")

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


class CodexSenderWithoutHerdrSessionTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    """herdr learns a Codex conversation only from a SessionStart hook; when it
    never arrives, Codex's own thread record must still identify the worker."""

    def setUp(self) -> None:
        super().setUp()
        self.instruction_path, _ = self.write_dispatch("codex")
        instruction = json.loads(self.instruction_path.read_text())
        instruction.update(
            status="in-progress", session_id=None,
            herdr_pane_id="worker-pane", herdr_terminal_id="terminal-worker-pane",
        )
        self.instruction_path.write_text(json.dumps(instruction))
        stem = self.instruction_path.name.removesuffix(".json")
        self.status_path = self.instruction_path.with_name(f"{stem}.status.json")
        opening = contract_prompt_line(instruction["contract_path"]) + "Begin contract task.\n"
        codex_home = self.home / ".codex"
        codex_home.mkdir()
        with sqlite3.connect(codex_home / "state_5.sqlite") as connection:
            connection.execute(
                "CREATE TABLE threads (id TEXT PRIMARY KEY, source TEXT NOT NULL, "
                "first_user_message TEXT NOT NULL DEFAULT '')"
            )
            connection.executemany(
                "INSERT INTO threads VALUES (?, ?, ?)",
                [
                    ("worker-thread", "cli", opening),
                    ("subagent-thread", '{"subagent":"review"}', opening),
                    ("other-worker-thread", "cli", "Before any task action, read and "
                     "follow the mandatory contract at /elsewhere.contract.md.\n"),
                ],
            )
        connection.close()
        self.fake_bin, self.capture = self.install_fake_herdr()
        self.env = {
            "PATH": f"{self.fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(self.capture),
            "HERDR_PANE_ID": "worker-pane",
            "HERDR_AGENT_KINDS": json.dumps({"worker-pane": "codex", "main-pane": "claude"}),
            "HERDR_SESSIONS": json.dumps({"main-pane": "main-session"}),
            "HERDR_SESSIONLESS_PANES": json.dumps(["worker-pane"]),
            "CODEX_HOME": str(codex_home),
        }

    def report(self, thread_id: str) -> "subprocess.CompletedProcess[str]":
        return self.run_script(
            "report-task-status.py", "--instruction-path", str(self.instruction_path),
            "--status", "done", "--note", "Work verified.",
            extra_env={**self.env, "CODEX_THREAD_ID": thread_id},
        )

    def test_worker_thread_opened_on_its_contract_reports(self) -> None:
        result = self.report("worker-thread")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.status_path.read_text())["status"], "done")

    def test_other_threads_stay_refused(self) -> None:
        for thread_id in ("subagent-thread", "other-worker-thread", "unknown-thread"):
            with self.subTest(thread_id=thread_id):
                result = self.report(thread_id)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("sender thread", result.stderr)
                self.assertFalse(self.status_path.exists())

    def test_coordinator_records_status_for_a_live_worker_that_cannot_report(self) -> None:
        main_env = {**self.env, "HERDR_PANE_ID": "main-pane", "CODEX_THREAD_ID": ""}
        recover = [
            "recover-task-status.py", "--instruction-path", str(self.instruction_path),
            "--status", "done", "--note", "Worker committed and verified; its report was refused.",
        ]
        closing = ["close-worker-pane.py", "--instruction-path", str(self.instruction_path)]

        refused_close = self.run_script(*closing, extra_env=main_env)
        self.assertNotEqual(refused_close.returncode, 0, refused_close.stdout)
        self.assertIn("--worker-cannot-report", refused_close.stderr)
        refused = self.run_script(*recover, extra_env=main_env)
        self.assertNotEqual(refused.returncode, 0, refused.stdout)
        self.assertIn("--worker-cannot-report", refused.stderr)
        working = self.run_script(
            *recover, "--worker-cannot-report",
            extra_env={**main_env, "HERDR_AGENT_STATUSES": json.dumps({"worker-pane": "working"})},
        )
        self.assertNotEqual(working.returncode, 0, working.stdout)
        self.assertIn("still working", working.stderr)
        self.assertFalse(self.status_path.exists())
        impersonated = self.run_script(*recover, "--worker-cannot-report", extra_env=self.env)
        self.assertNotEqual(impersonated.returncode, 0, impersonated.stdout)
        self.assertFalse(self.status_path.exists())

        recovered = self.run_script(*recover, "--worker-cannot-report", extra_env=main_env)
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        status = json.loads(self.status_path.read_text())
        self.assertEqual(status["status"], "done")
        self.assertIs(status["recovered_by_main_agent"], True)
        self.assertIs(status["worker_live_at_recovery"], True)
        self.assertNotIn("herdr_pane_closed_at", json.loads(self.instruction_path.read_text()))

        closed = self.run_script(*closing, extra_env=main_env)
        self.assertEqual(closed.returncode, 0, closed.stderr)
        self.assertEqual(json.loads(closed.stdout)["closed_pane_id"], "worker-pane")
