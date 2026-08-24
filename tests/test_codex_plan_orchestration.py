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

    def dispatch(self, agent_kind: str, task_id: str = "t1") -> Path:
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
            "--main-agent-peer-name",
            "test-orchestrator",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(json.loads(result.stdout)["instruction_path"])

    def test_codex_plan_dispatch_records_kind_and_marks_task_dispatched(self) -> None:
        instruction_path = self.dispatch("codex")

        instruction = json.loads(instruction_path.read_text())
        plan = json.loads(self.plan_path.read_text())
        self.assertEqual(instruction["agent_kind"], "codex")
        self.assertEqual(instruction["task_id"], "t1")
        self.assertEqual(plan["tasks"][0]["status"], "dispatched")

    def test_codex_plan_dispatch_does_not_require_claude_peer_name(self) -> None:
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
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        instruction = json.loads(Path(json.loads(result.stdout)["instruction_path"]).read_text())
        self.assertIsNone(instruction["main_agent_send_message_peer"])

    def test_codex_done_status_unblocks_dependent_task(self) -> None:
        instruction_path = self.dispatch("codex")
        report = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "done",
            "--note",
            "Codex prerequisite complete",
        )
        self.assertEqual(report.returncode, 0, report.stderr)

        ready = self.run_script(
            "read-plan-status.py", "--plan", self.plan_slug, "--ready"
        )
        self.assertEqual(ready.returncode, 0, ready.stderr)
        self.assertEqual([task["task_id"] for task in json.loads(ready.stdout)], ["t2"])

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
            "  get) printf '%s\\n' '{\"result\":{\"agent\":{\"name\":\"codex-task\"}}}' ;;\n"
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
            extra_env={"PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        updated = json.loads(status_path.read_text())
        self.assertEqual(updated["main_agent_reply"], "continue with the dependency")
        self.assertIn("resolved_by_main_agent_at", updated)

    def test_existing_claude_plan_dispatch_remains_supported(self) -> None:
        instruction_path = self.dispatch("claude")
        self.assertEqual(json.loads(instruction_path.read_text())["agent_kind"], "claude")

    def test_claude_dispatch_still_requires_send_message_peer_name(self) -> None:
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
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--main-agent-peer-name is required", result.stderr)


if __name__ == "__main__":
    unittest.main()
