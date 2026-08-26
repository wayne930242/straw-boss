from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class CodexPlanOrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        self.plan_slug = "mixed-plan"
        self.plan_dir = self.home / ".straw-boss" / "plans" / self.plan_slug
        (self.plan_dir / "status").mkdir(parents=True)
        (self.home / ".straw-boss" / "dispatch").mkdir(parents=True)
        self.plan_path = self.plan_dir / "plan.json"
        self.plan_path.write_text(
            json.dumps(
                {
                    "plan_id": f"p-{self.plan_slug}",
                    "status": "planning",
                    "tasks": [
                        {
                            "task_id": "t1",
                            "app": "api",
                            "description": "produce the prerequisite",
                            "depends_on": [],
                            "status": "planned",
                        },
                        {
                            "task_id": "t2",
                            "app": "web",
                            "description": "consume the prerequisite",
                            "depends_on": ["t1"],
                            "status": "planned",
                        },
                    ],
                },
                indent=2,
            )
            + "\n"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_peer_questions_use_the_script_owned_transport(self) -> None:
        skill = (ROOT / "skills" / "asking-peer-agents" / "SKILL.md").read_text()

        self.assertIn("send-dispatch-message.py", skill)
        self.assertNotIn("SendMessage", skill)
        self.assertNotIn("herdr agent prompt", skill)

    def run_script(
        self,
        script_name: str,
        *args: str,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "HOME": str(self.home)}
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script_name), *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def dispatch(
        self,
        agent_kind: str,
        task_id: str = "t1",
        main_agent_kind: str = "codex",
    ) -> Path:
        result = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-{task_id}",
            "--task",
            "Run the task and report status through the instruction path.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(ROOT),
            "--plan",
            self.plan_slug,
            "--task-id",
            task_id,
            "--agent-kind",
            agent_kind,
            "--main-agent-kind",
            main_agent_kind,
            "--main-agent-pane-id",
            "main:pane",
            "--main-agent-session-id",
            "main-session",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        instruction_path = Path(json.loads(result.stdout)["instruction_path"])
        instruction = json.loads(instruction_path.read_text())
        instruction["status"] = "in-progress"
        instruction["herdr_pane_id"] = "worker:pane"
        instruction["session_id"] = "worker-session"
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")
        return instruction_path

    def test_codex_plan_dispatch_records_kind_and_marks_task_dispatched(self) -> None:
        instruction_path = self.dispatch("codex")

        instruction = json.loads(instruction_path.read_text())
        plan = json.loads(self.plan_path.read_text())
        self.assertEqual(instruction["agent_kind"], "codex")
        self.assertEqual(instruction["main_agent_kind"], "codex")
        self.assertEqual(instruction["task_id"], "t1")
        self.assertEqual(plan["tasks"][0]["status"], "dispatched")

    def test_codex_plan_dispatch_records_main_session_fingerprint(self) -> None:
        result = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1",
            "--task",
            "Run the task and report status through the instruction path.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(ROOT),
            "--plan",
            self.plan_slug,
            "--task-id",
            "t1",
            "--agent-kind",
            "codex",
            "--main-agent-kind",
            "codex",
            "--main-agent-pane-id",
            "main:pane",
            "--main-agent-session-id",
            "main-session",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        instruction = json.loads(Path(json.loads(result.stdout)["instruction_path"]).read_text())
        self.assertEqual(instruction["main_agent_session_id"], "main-session")
        self.assertNotIn("main_agent_send_message_peer", instruction)

    def test_codex_done_status_unblocks_dependent_task(self) -> None:
        instruction_path = self.dispatch("codex")
        fake_bin = self.home / "bin"
        fake_bin.mkdir()
        capture_path = self.home / "herdr-call.txt"
        fake_herdr = fake_bin / "herdr"
        fake_herdr.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" > \"$HERDR_CAPTURE\"\n"
            "if [ \"$2\" = get ]; then\n"
            "  if [ \"$3\" = 'worker:pane' ]; then session='worker-session'; else session='main-session'; fi\n"
            "  printf '%s\\n' \"{\\\"result\\\":{\\\"agent\\\":{\\\"agent_session\\\":{\\\"value\\\":\\\"$session\\\"}}}}\"\n"
            "else\n"
            "  [ -f \"$EXPECTED_STATUS_PATH\" ] || exit 9\n"
            "  printf '%s\\n' '{\"result\":{}}'\n"
            "fi\n"
        )
        fake_herdr.chmod(0o755)
        report = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "done",
            "--note",
            "Codex prerequisite complete",
            "--ref",
            "tests/test_codex_plan_orchestration.py",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "EXPECTED_STATUS_PATH": str(self.plan_dir / "status" / "t1.json"),
                "HERDR_CAPTURE": str(capture_path),
                "HERDR_PANE_ID": "worker:pane",
            },
        )
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("agent prompt main:pane", capture_path.read_text())
        self.assertIn("status from=api/t1", capture_path.read_text())
        self.assertIn("done — Codex prerequisite complete", capture_path.read_text())
        self.assertIn('refs=["tests/test_codex_plan_orchestration.py"]', capture_path.read_text())
        self.assertIn("Codex prerequisite complete", capture_path.read_text())
        persisted = json.loads((self.plan_dir / "status" / "t1.json").read_text())
        self.assertEqual(persisted["refs"], ["tests/test_codex_plan_orchestration.py"])

        ready = self.run_script(
            "read-plan-status.py", "--plan", self.plan_slug, "--ready"
        )
        self.assertEqual(ready.returncode, 0, ready.stderr)
        self.assertEqual([task["task_id"] for task in json.loads(ready.stdout)], ["t2"])

    def test_failed_status_notifies_main_agent_through_herdr(self) -> None:
        instruction_path = self.dispatch("codex")
        fake_bin = self.home / "bin"
        fake_bin.mkdir()
        capture_path = self.home / "failed-herdr-call.txt"
        fake_herdr = fake_bin / "herdr"
        fake_herdr.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" > \"$HERDR_CAPTURE\"\n"
            "if [ \"$2\" = get ]; then\n"
            "  if [ \"$3\" = 'worker:pane' ]; then session='worker-session'; else session='main-session'; fi\n"
            "  printf '%s\\n' \"{\\\"result\\\":{\\\"agent\\\":{\\\"agent_session\\\":{\\\"value\\\":\\\"$session\\\"}}}}\"\n"
            "else\n"
            "  printf '%s\\n' '{\"result\":{}}'\n"
            "fi\n"
        )
        fake_herdr.chmod(0o755)

        report = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "failed",
            "--note",
            "Dependency contract is invalid",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture_path),
                "HERDR_PANE_ID": "worker:pane",
            },
        )

        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("agent prompt main:pane", capture_path.read_text())
        self.assertIn("failed — Dependency contract is invalid", capture_path.read_text())
        persisted = json.loads((self.plan_dir / "status" / "t1.json").read_text())
        self.assertEqual(persisted["status"], "failed")

    def test_status_watcher_emits_every_content_transition_and_recovers_on_restart(self) -> None:
        watcher_path = SCRIPTS / "watch-plan-status.py"
        self.assertTrue(watcher_path.is_file(), "watch-plan-status.py must exist")
        spec = importlib.util.spec_from_file_location("watch_plan_status", watcher_path)
        assert spec is not None and spec.loader is not None
        watcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(watcher)

        status_path = self.plan_dir / "status" / "t1.json"
        status_path.write_text(
            json.dumps({"status": "awaiting-main-agent", "note": "need input", "timestamp": "1"})
        )
        seen: dict[str, str] = {}
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            first = watcher.collect_status_changes(self.plan_slug, seen)
        self.assertEqual([event["status"] for event in first], ["awaiting-main-agent"])

        status_path.write_text(json.dumps({"status": "done", "note": "resumed", "timestamp": "2"}))
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            second = watcher.collect_status_changes(self.plan_slug, seen)
        self.assertEqual([event["status"] for event in second], ["done"])

        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            recovered = watcher.collect_status_changes(self.plan_slug, {})
        self.assertEqual([event["status"] for event in recovered], ["done"])

    def test_status_watcher_retries_a_partially_written_status_file(self) -> None:
        watcher_path = SCRIPTS / "watch-plan-status.py"
        spec = importlib.util.spec_from_file_location("watch_plan_status_partial", watcher_path)
        assert spec is not None and spec.loader is not None
        watcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(watcher)

        status_path = self.plan_dir / "status" / "t1.json"
        status_path.write_text('{"status": "done"')
        seen: dict[str, str] = {}
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            self.assertEqual(watcher.collect_status_changes(self.plan_slug, seen), [])
        self.assertEqual(seen, {})

        status_path.write_text(json.dumps({"status": "done", "note": "complete"}))
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            recovered = watcher.collect_status_changes(self.plan_slug, seen)
        self.assertEqual([event["status"] for event in recovered], ["done"])

    def test_status_watcher_uses_filename_as_the_authoritative_task_id(self) -> None:
        watcher_path = SCRIPTS / "watch-plan-status.py"
        spec = importlib.util.spec_from_file_location("watch_plan_status_task_id", watcher_path)
        assert spec is not None and spec.loader is not None
        watcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(watcher)

        status_path = self.plan_dir / "status" / "t1.json"
        status_path.write_text(json.dumps({"task_id": "t2", "status": "done"}))
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            events = watcher.collect_status_changes(self.plan_slug, {})
        self.assertEqual(events[0]["task_id"], "t1")

    def test_reply_to_worker_accepts_codex_herdr_pane(self) -> None:
        instruction_path = self.dispatch("codex")
        instruction = json.loads(instruction_path.read_text())
        instruction["status"] = "in-progress"
        instruction["herdr_pane_id"] = "w1:p2"
        instruction["session_id"] = "worker-session"
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")
        status_path = self.plan_dir / "status" / "t1.json"
        status_path.write_text(
            json.dumps(
                {"status": "awaiting-main-agent", "note": "need arbitration", "timestamp": "1"},
                indent=2,
            )
            + "\n"
        )

        fake_bin = self.home / "bin"
        fake_bin.mkdir()
        fake_herdr = fake_bin / "herdr"
        fake_herdr.write_text(
            "#!/bin/sh\n"
            "case \"$2\" in\n"
            "  get) if [ \"$3\" = 'main:pane' ]; then session='main-session'; else session='worker-session'; fi; printf '%s\\n' \"{\\\"result\\\":{\\\"agent\\\":{\\\"name\\\":\\\"codex-task\\\",\\\"agent_session\\\":{\\\"value\\\":\\\"$session\\\"}}}}\" ;;\n"
            "  prompt) printf '%s\\n' '{\"result\":{}}' ;;\n"
            "  read) printf '%s\\n' 'continue with the dependency' ;;\n"
            "  *) exit 2 ;;\n"
            "esac\n"
        )
        fake_herdr.chmod(0o755)

        result = self.run_script(
            "reply-to-worker.py",
            "--worker-instruction-path",
            str(instruction_path),
            "--reply",
            "continue with the dependency",
            "--ref",
            "plan://mixed-plan/t2",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_PANE_ID": "main:pane",
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        updated = json.loads(status_path.read_text())
        self.assertEqual(updated["main_agent_reply"], "continue with the dependency")
        self.assertEqual(updated["main_agent_reply_refs"], ["plan://mixed-plan/t2"])
        self.assertIn("resolved_by_main_agent_at", updated)

    def test_claude_worker_reports_to_codex_main_through_shared_transport(self) -> None:
        instruction_path = self.dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        self.assertEqual(instruction["agent_kind"], "claude")
        self.assertEqual(instruction["main_agent_kind"], "codex")
        self.assertNotIn("main_agent_send_message_peer", instruction)
        self.assertEqual(instruction["main_agent_session_id"], "main-session")

        fake_bin = self.home / "bin"
        fake_bin.mkdir()
        capture_path = self.home / "claude-to-codex-herdr.txt"
        fake_herdr = fake_bin / "herdr"
        fake_herdr.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" > \"$HERDR_CAPTURE\"\n"
            "if [ \"$2\" = get ]; then\n"
            "  if [ \"$3\" = 'worker:pane' ]; then session='worker-session'; else session='main-session'; fi\n"
            "  printf '%s\\n' \"{\\\"result\\\":{\\\"agent\\\":{\\\"agent_session\\\":{\\\"value\\\":\\\"$session\\\"}}}}\"\n"
            "else\n"
            "  printf '%s\\n' '{\"result\":{}}'\n"
            "fi\n"
        )
        fake_herdr.chmod(0o755)
        report = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "done",
            "--note",
            "Claude worker finished for Codex main",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture_path),
                "HERDR_PANE_ID": "worker:pane",
            },
        )
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("agent prompt main:pane", capture_path.read_text())
        self.assertIn("status from=api/t1", capture_path.read_text())
        self.assertNotIn("from claude dispatched agent", capture_path.read_text())

    def test_herdr_notification_failure_keeps_durable_status(self) -> None:
        instruction_path = self.dispatch("codex")
        fake_bin = self.home / "bin"
        fake_bin.mkdir()
        fake_herdr = fake_bin / "herdr"
        fake_herdr.write_text(
            "#!/bin/sh\n"
            "if [ \"$2\" = get ] && [ \"$3\" = 'worker:pane' ]; then\n"
            "  printf '%s\\n' '{\"result\":{\"agent\":{\"agent_session\":{\"value\":\"worker-session\"}}}}'\n"
            "  exit 0\n"
            "fi\n"
            "exit 7\n"
        )
        fake_herdr.chmod(0o755)

        report = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "failed",
            "--note",
            "delivery failed after persistence",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_PANE_ID": "worker:pane",
            },
        )

        self.assertNotEqual(report.returncode, 0)
        self.assertIn("status remains written", report.stderr)
        status = json.loads((self.plan_dir / "status" / "t1.json").read_text())
        self.assertEqual(status["status"], "failed")

    def test_main_agent_cancel_does_not_notify_itself(self) -> None:
        instruction_path = self.dispatch("codex")
        fake_bin = self.home / "bin"
        fake_bin.mkdir()
        fake_herdr = fake_bin / "herdr"
        fake_herdr.write_text(
            "#!/bin/sh\n"
            "if [ \"$2\" = get ] && [ \"$3\" = 'main:pane' ]; then\n"
            "  printf '%s\\n' '{\"result\":{\"agent\":{\"agent_session\":{\"value\":\"main-session\"}}}}'\n"
            "  exit 0\n"
            "fi\n"
            "exit 7\n"
        )
        fake_herdr.chmod(0o755)

        report = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "cancelled",
            "--note",
            "main agent cancelled the dispatch",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_PANE_ID": "main:pane",
            },
        )

        self.assertEqual(report.returncode, 0, report.stderr)
        status = json.loads((self.plan_dir / "status" / "t1.json").read_text())
        self.assertEqual(status["status"], "cancelled")

    def test_dispatch_cli_no_longer_exposes_send_message_peer(self) -> None:
        result = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1",
            "--task",
            "Run the task.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(ROOT),
            "--plan",
            self.plan_slug,
            "--task-id",
            "t1",
            "--agent-kind",
            "claude",
            "--main-agent-kind",
            "codex",
            "--main-agent-pane-id",
            "main:pane",
            "--main-agent-peer-name",
            "not-a-codex-channel",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized arguments: --main-agent-peer-name", result.stderr)

    def test_headless_dispatch_has_durable_contract_without_a_live_endpoint(self) -> None:
        result = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1",
            "--task",
            "Run the task.",
            "--mode",
            "claude-p",
            "--repo-root",
            str(ROOT),
            "--plan",
            self.plan_slug,
            "--task-id",
            "t1",
            "--agent-kind",
            "claude",
            "--main-agent-kind",
            "claude",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        instruction_path = Path(json.loads(result.stdout)["instruction_path"])
        instruction = json.loads(instruction_path.read_text())
        self.assertIsNone(instruction["main_agent_herdr_pane_id"])
        self.assertIsNone(instruction["main_agent_session_id"])
        self.assertTrue(Path(instruction["contract_path"]).is_file())

    def test_herdr_dispatch_requires_main_agent_pane(self) -> None:
        result = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1",
            "--task",
            "Run the task.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(ROOT),
            "--plan",
            self.plan_slug,
            "--task-id",
            "t1",
            "--agent-kind",
            "codex",
            "--main-agent-kind",
            "claude",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--main-agent-pane-id is required", result.stderr)


if __name__ == "__main__":
    unittest.main()
