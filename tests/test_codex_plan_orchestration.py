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
        args = [
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
        ]
        if main_agent_kind == "claude":
            args.extend(["--main-agent-session-id", "main-session"])
        else:
            args.extend(["--main-agent-terminal-id", "terminal-main-pane"])
        result = self.run_script(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        instruction_path = Path(json.loads(result.stdout)["instruction_path"])
        instruction = json.loads(instruction_path.read_text())
        instruction["status"] = "in-progress"
        instruction["herdr_pane_id"] = "worker:pane"
        if agent_kind == "claude":
            instruction["session_id"] = "worker-session"
        else:
            instruction["session_id"] = None
            instruction["herdr_terminal_id"] = "terminal-worker-pane"
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

    def test_codex_plan_dispatch_records_main_terminal_fingerprint(self) -> None:
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
            "--main-agent-terminal-id",
            "terminal-main-pane",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        instruction = json.loads(Path(json.loads(result.stdout)["instruction_path"]).read_text())
        self.assertIsNone(instruction["main_agent_session_id"])
        self.assertEqual(
            instruction["main_agent_herdr_terminal_id"], "terminal-main-pane"
        )
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
            "  if [ \"$3\" = 'worker:pane' ]; then terminal='terminal-worker-pane'; else terminal='terminal-main-pane'; fi\n"
            "  printf '%s\\n' \"{\\\"result\\\":{\\\"agent\\\":{\\\"agent\\\":\\\"codex\\\",\\\"pane_id\\\":\\\"$3\\\",\\\"terminal_id\\\":\\\"$terminal\\\"}}}\"\n"
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
            "  if [ \"$3\" = 'worker:pane' ]; then terminal='terminal-worker-pane'; else terminal='terminal-main-pane'; fi\n"
            "  printf '%s\\n' \"{\\\"result\\\":{\\\"agent\\\":{\\\"agent\\\":\\\"codex\\\",\\\"pane_id\\\":\\\"$3\\\",\\\"terminal_id\\\":\\\"$terminal\\\"}}}\"\n"
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
        instruction["session_id"] = None
        instruction["herdr_terminal_id"] = "terminal-worker-pane"
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
            "  get) if [ \"$3\" = 'main:pane' ]; then terminal='terminal-main-pane'; else terminal='terminal-worker-pane'; fi; printf '%s\\n' \"{\\\"result\\\":{\\\"agent\\\":{\\\"name\\\":\\\"codex-task\\\",\\\"agent\\\":\\\"codex\\\",\\\"pane_id\\\":\\\"$3\\\",\\\"terminal_id\\\":\\\"$terminal\\\"}}}\" ;;\n"
            "  prompt) printf '%s\\n' '{\"result\":{}}' ;;\n"
            "  read) printf '%s\\n' 'continue with' 'the dependency' ;;\n"
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
        self.assertIsNone(instruction["main_agent_session_id"])
        self.assertEqual(
            instruction["main_agent_herdr_terminal_id"], "terminal-main-pane"
        )

        fake_bin = self.home / "bin"
        fake_bin.mkdir()
        capture_path = self.home / "claude-to-codex-herdr.txt"
        fake_herdr = fake_bin / "herdr"
        fake_herdr.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" > \"$HERDR_CAPTURE\"\n"
            "if [ \"$2\" = get ]; then\n"
            "  if [ \"$3\" = 'worker:pane' ]; then\n"
            "    printf '%s\\n' '{\"result\":{\"agent\":{\"agent\":\"claude\",\"pane_id\":\"worker:pane\",\"agent_session\":{\"value\":\"worker-session\"}}}}'\n"
            "  else\n"
            "    printf '%s\\n' '{\"result\":{\"agent\":{\"agent\":\"codex\",\"pane_id\":\"main:pane\",\"terminal_id\":\"terminal-main-pane\"}}}'\n"
            "  fi\n"
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
            "  printf '%s\\n' '{\"result\":{\"agent\":{\"agent\":\"codex\",\"pane_id\":\"worker:pane\",\"terminal_id\":\"terminal-worker-pane\"}}}'\n"
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
            "  printf '%s\\n' '{\"result\":{\"agent\":{\"agent\":\"codex\",\"pane_id\":\"main:pane\",\"terminal_id\":\"terminal-main-pane\"}}}'\n"
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
        contract = Path(instruction["contract_path"]).read_text()
        self.assertIn("cannot resume after it exits", contract)
        self.assertIn("--status failed", contract)
        self.assertNotIn("--status <checkpoint>", contract)
        self.assertNotIn("After a checkpoint reply", contract)

    def test_headless_codex_contract_persists_a_resumable_checkpoint(self) -> None:
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
            "codex",
            "--main-agent-kind",
            "claude",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        instruction_path = Path(json.loads(result.stdout)["instruction_path"])
        contract = Path(json.loads(instruction_path.read_text())["contract_path"]).read_text()
        self.assertIn("resumes this recorded Codex thread", contract)
        self.assertIn("--status <checkpoint>", contract)
        self.assertIn("do not overwrite the checkpoint", contract)

    def test_headless_codex_runner_records_and_resumes_the_provider_thread(
        self,
    ) -> None:
        written = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1",
            "--task",
            "Ask one decision, then finish after the answer.",
            "--mode",
            "claude-p",
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
        self.assertEqual(written.returncode, 0, written.stderr)
        instruction_path = Path(json.loads(written.stdout)["instruction_path"])
        status_path = self.plan_dir / "status" / "t1.json"
        fake_bin = self.home / "bin"
        fake_bin.mkdir()
        capture = self.home / "codex-calls.jsonl"
        fake_codex = fake_bin / "codex"
        fake_codex.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "with open(os.environ['CODEX_CAPTURE'], 'a') as stream:\n"
            "    stream.write(json.dumps(args) + '\\n')\n"
            "print(json.dumps({'type': 'thread.started', 'thread_id': 'thread-123'}))\n"
            "status = 'done' if args[:2] == ['exec', 'resume'] else 'awaiting-user-input'\n"
            "Path(os.environ['CODEX_STATUS_PATH']).write_text(json.dumps({'status': status, 'note': 'choose A' if status != 'done' else 'finished'}))\n"
        )
        fake_codex.chmod(0o755)
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "CODEX_CAPTURE": str(capture),
            "CODEX_STATUS_PATH": str(status_path),
        }

        started = self.run_script(
            "run-headless-dispatched-agent.py",
            "start",
            "--instruction-path",
            str(instruction_path),
            extra_env=env,
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        instruction = json.loads(instruction_path.read_text())
        self.assertEqual(instruction["provider_thread_id"], "thread-123")
        self.assertEqual(instruction["status"], "in-progress")
        self.assertEqual(json.loads(status_path.read_text())["status"], "awaiting-user-input")

        resumed = self.run_script(
            "run-headless-dispatched-agent.py",
            "resume",
            "--instruction-path",
            str(instruction_path),
            "--answer",
            "Use option A.",
            extra_env=env,
        )
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(json.loads(status_path.read_text())["status"], "done")
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(calls[0][:2], ["exec", "--json"])
        self.assertEqual(calls[1][:2], ["exec", "resume"])
        self.assertIn("thread-123", calls[1])
        self.assertEqual(calls[1][-1], "Use option A.")

    def test_one_process_claim_blocks_duplicate_headless_start_and_resume(
        self,
    ) -> None:
        written = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1",
            "--task",
            "Ask one decision, then finish after the answer.",
            "--mode",
            "claude-p",
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
        self.assertEqual(written.returncode, 0, written.stderr)
        instruction_path = Path(json.loads(written.stdout)["instruction_path"])
        runner_path = SCRIPTS / "run-headless-dispatched-agent.py"
        spec = importlib.util.spec_from_file_location("headless_claim_test", runner_path)
        assert spec is not None and spec.loader is not None
        runner = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(SCRIPTS))
        try:
            spec.loader.exec_module(runner)
        finally:
            sys.path.pop(0)

        with runner.headless_claim(instruction_path, "test-start"):
            duplicate_start = self.run_script(
                "run-headless-dispatched-agent.py",
                "start",
                "--instruction-path",
                str(instruction_path),
            )
        self.assertNotEqual(duplicate_start.returncode, 0)
        self.assertIn("another headless operation already owns", duplicate_start.stderr)

        instruction = json.loads(instruction_path.read_text())
        instruction["status"] = "in-progress"
        instruction["provider_thread_id"] = "thread-123"
        instruction["headless_resume_args"] = []
        instruction_path.write_text(json.dumps(instruction))
        (self.plan_dir / "status" / "t1.json").write_text(
            json.dumps({"status": "awaiting-user-input", "note": "choose A"})
        )
        with runner.headless_claim(instruction_path, "test-resume"):
            duplicate_resume = self.run_script(
                "run-headless-dispatched-agent.py",
                "resume",
                "--instruction-path",
                str(instruction_path),
                "--answer",
                "Use option A.",
            )
        self.assertNotEqual(duplicate_resume.returncode, 0)
        self.assertIn("another headless operation already owns", duplicate_resume.stderr)

    def test_wrapped_headless_claude_failure_can_be_retried_with_a_fresh_slug(
        self,
    ) -> None:
        first = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1",
            "--task",
            "Ask for the missing decision.",
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
        self.assertEqual(first.returncode, 0, first.stderr)
        status_path = self.plan_dir / "status" / "t1.json"
        status_path.write_text(
            json.dumps({"status": "failed", "note": "Need one user decision."})
        )
        wrapped = self.run_script(
            "wrap-up-task.py",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1",
            "--plan",
            self.plan_slug,
            "--task-id",
            "t1",
        )
        self.assertEqual(wrapped.returncode, 0, wrapped.stderr)

        same_slug = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1",
            "--task",
            "Continue with option A.",
            "--mode",
            "claude-p",
            "--repo-root",
            str(ROOT),
            "--plan",
            self.plan_slug,
            "--task-id",
            "t1",
            "--retry-failed-plan-task",
            "--agent-kind",
            "claude",
            "--main-agent-kind",
            "claude",
        )
        self.assertNotEqual(same_slug.returncode, 0)
        self.assertIn("fresh dispatch slug", same_slug.stderr)

        wrong_app = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "web",
            "--slug",
            f"{self.plan_slug}-t1-retry-2",
            "--task",
            "Continue with option A.",
            "--mode",
            "claude-p",
            "--repo-root",
            str(ROOT),
            "--plan",
            self.plan_slug,
            "--task-id",
            "t1",
            "--retry-failed-plan-task",
            "--agent-kind",
            "claude",
            "--main-agent-kind",
            "claude",
        )
        self.assertNotEqual(wrong_app.returncode, 0)
        self.assertIn("wrapped attempt's app", wrong_app.stderr)

        retry = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1-retry-2",
            "--task",
            "Continue with the user's confirmed answer: use option A.",
            "--mode",
            "claude-p",
            "--repo-root",
            str(ROOT),
            "--plan",
            self.plan_slug,
            "--task-id",
            "t1",
            "--retry-failed-plan-task",
            "--agent-kind",
            "claude",
            "--main-agent-kind",
            "claude",
        )

        self.assertEqual(retry.returncode, 0, retry.stderr)
        self.assertFalse(status_path.exists())
        plan = json.loads(self.plan_path.read_text())
        self.assertEqual(plan["tasks"][0]["status"], "dispatched")
        instruction = json.loads(Path(json.loads(retry.stdout)["instruction_path"]).read_text())
        self.assertIn("confirmed answer", instruction["task"])

    def test_failed_plan_retry_requires_the_previous_attempt_to_be_wrapped(self) -> None:
        first = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1",
            "--task",
            "Ask for the missing decision.",
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
        self.assertEqual(first.returncode, 0, first.stderr)
        (self.plan_dir / "status" / "t1.json").write_text(
            json.dumps({"status": "failed", "note": "Need one decision."})
        )

        retry = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1-retry-2",
            "--task",
            "Continue with option A.",
            "--mode",
            "claude-p",
            "--repo-root",
            str(ROOT),
            "--plan",
            self.plan_slug,
            "--task-id",
            "t1",
            "--retry-failed-plan-task",
            "--agent-kind",
            "claude",
            "--main-agent-kind",
            "claude",
        )

        self.assertNotEqual(retry.returncode, 0)
        self.assertIn("not a wrapped failed task", retry.stderr)

    def test_failed_plan_retry_is_only_for_headless_claude(self) -> None:
        retry = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1-retry-2",
            "--task",
            "Continue with option A.",
            "--mode",
            "claude-p",
            "--repo-root",
            str(ROOT),
            "--plan",
            self.plan_slug,
            "--task-id",
            "t1",
            "--retry-failed-plan-task",
            "--agent-kind",
            "codex",
            "--main-agent-kind",
            "claude",
        )

        self.assertNotEqual(retry.returncode, 0)
        self.assertIn("only for a headless Claude attempt", retry.stderr)

    def test_failed_plan_retry_rejects_a_live_previous_instruction(self) -> None:
        first = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1",
            "--task",
            "Ask for the missing decision.",
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
        self.assertEqual(first.returncode, 0, first.stderr)
        plan = json.loads(self.plan_path.read_text())
        plan["tasks"][0]["status"] = "failed"
        self.plan_path.write_text(json.dumps(plan))
        (self.plan_dir / "status" / "t1.json").write_text(
            json.dumps({"status": "failed", "note": "Need one decision."})
        )

        retry = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"{self.plan_slug}-t1-retry-2",
            "--task",
            "Continue with option A.",
            "--mode",
            "claude-p",
            "--repo-root",
            str(ROOT),
            "--plan",
            self.plan_slug,
            "--task-id",
            "t1",
            "--retry-failed-plan-task",
            "--agent-kind",
            "claude",
            "--main-agent-kind",
            "claude",
        )

        self.assertNotEqual(retry.returncode, 0)
        self.assertIn("still has live instruction", retry.stderr)

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
