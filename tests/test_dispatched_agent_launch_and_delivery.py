from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import (
    ROOT,
    SCRIPTS,
    DispatchedAgentLifecycleFixture,
)


class DispatchedAgentLaunchAndDeliveryTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def test_launcher_injects_claude_contract_and_records_receipt(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_LIVE_SESSION": str(instruction["session_id"]),
        }

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "api-worker",
            extra_env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertIn(["pane", "get", "main-pane"], calls)
        self.assertIn(
            [
                "pane",
                "split",
                "main-pane",
                "--direction",
                "right",
                "--cwd",
                str(ROOT),
                "--no-focus",
            ],
            calls,
        )
        self.assertFalse(any(call and call[0] == "tab" for call in calls))
        start = next(call for call in calls if call[:2] == ["agent", "start"])
        contract_path = str(instruction["contract_path"])
        self.assertIn("--append-system-prompt-file", start)
        self.assertEqual(start[start.index("--append-system-prompt-file") + 1], contract_path)
        self.assertTrue(any(call[:2] == ["agent", "prompt"] for call in calls))

        receipt_path = instruction_path.with_name("api--contract-claude.launch.json")
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["contract_sha256"], instruction["contract_sha256"])
        self.assertEqual(receipt["session_id"], instruction["session_id"])
        self.assertEqual(receipt["pane_id"], "worker-pane")
        self.assertEqual(receipt["tab_id"], "tab-1")

    def test_launcher_applies_claude_profile_model_effort_and_advisor(self) -> None:
        instruction_path, _ = self.write_dispatch(
            "claude",
            agent_profile="worker",
            agent_model="sonnet",
            agent_effort="high",
            advisor_model="opus",
        )
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "profiled-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        start = next(call for call in calls if call[:2] == ["agent", "start"])
        for flag, value in (
            ("--agent", "worker"),
            ("--model", "sonnet"),
            ("--effort", "high"),
            ("--advisor", "opus"),
        ):
            self.assertEqual(start.count(flag), 1)
            self.assertEqual(start[start.index(flag) + 1], value)

    def test_launcher_injects_codex_developer_instructions(self) -> None:
        instruction_path, _ = self.write_dispatch("codex")
        instruction = json.loads(instruction_path.read_text())
        contract = Path(str(instruction["contract_path"])).read_text()
        fake_bin, capture = self.install_fake_herdr()
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_LIVE_SESSION": "codex-live-session",
        }

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "codex-worker",
            extra_env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        public_result = json.loads(result.stdout)
        self.assertNotIn("target_session_id", public_result)
        self.assertNotIn("pane_id", public_result)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        start = next(call for call in calls if call[:2] == ["agent", "start"])
        config_index = start.index("-c")
        developer_arg = start[config_index + 1]
        self.assertTrue(developer_arg.startswith("developer_instructions="))
        self.assertIn(str(instruction["contract_path"]), developer_arg)
        self.assertNotIn(contract, developer_arg)
        self.assertNotIn("\n", developer_arg)
        self.assertNotIn("`", developer_arg)

    def test_launcher_recovers_when_start_reports_a_live_blocked_agent(self) -> None:
        instruction_path, _ = self.write_dispatch("codex")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "blocked-codex-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_FAIL_START_BLOCKED": "1",
                "HERDR_LIVE_SESSION": "recovered-codex-session",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertTrue(any(call[:2] == ["agent", "send-keys"] for call in calls))
        self.assertTrue(any(call[:2] == ["agent", "wait"] for call in calls))
        self.assertTrue(any(call[:2] == ["agent", "prompt"] for call in calls))

    def test_launcher_retries_until_a_new_worker_pane_becomes_an_available_shell(
        self,
    ) -> None:
        instruction_path, _ = self.write_dispatch("codex")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "pane-readiness-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_PANE_BUSY_ATTEMPTS": "2",
                "HERDR_LIVE_SESSION": "pane-readiness-session",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        starts = [call for call in calls if call[:2] == ["agent", "start"]]
        self.assertEqual(len(starts), 3)
        self.assertNotIn(["pane", "close", "worker-pane"], calls)
        self.assertTrue(any(call[:2] == ["agent", "prompt"] for call in calls))

    def test_launcher_preserves_a_genuine_start_failure_and_closes_pane(self) -> None:
        instruction_path, _ = self.write_dispatch("codex")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "failed-codex-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_FAIL_START": "1",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("agent_start_failed", result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertIn(["pane", "close", "worker-pane"], calls)
        self.assertFalse(any(call[:2] == ["agent", "prompt"] for call in calls))

    def test_launcher_waits_for_claude_session_after_prompt(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "delayed-claude-session-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_SESSION_DELAY_GETS": "1",
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompt_index = next(
            index for index, call in enumerate(calls) if call[:2] == ["agent", "prompt"]
        )
        gets_after_prompt = [
            call for call in calls[prompt_index + 1 :] if call[:2] == ["agent", "get"]
        ]
        self.assertGreaterEqual(len(gets_after_prompt), 2)

    def test_launcher_records_codex_terminal_without_waiting_for_a_session(
        self,
    ) -> None:
        instruction_path, _ = self.write_dispatch("codex")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "sessionless-codex-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AGENT_KIND": "codex",
                "HERDR_TERMINAL_ID": "codex-terminal",
                "HERDR_OMIT_AGENT_SESSION": "1",
            },
            timeout_seconds=20,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(
            instruction_path.with_name("api--contract-codex.launch.json").read_text()
        )
        self.assertIsNone(receipt["session_id"])
        self.assertEqual(receipt["herdr_terminal_id"], "codex-terminal")

        confirmed = self.run_script(
            "dispatch-task.py",
            "confirm",
            "--app",
            "api",
            "--slug",
            "contract-codex",
        )
        self.assertEqual(confirmed.returncode, 0, confirmed.stderr)
        instruction = json.loads(instruction_path.read_text())
        self.assertEqual(instruction["status"], "in-progress")
        self.assertIsNone(instruction["session_id"])
        self.assertEqual(instruction["herdr_terminal_id"], "codex-terminal")

    def test_launcher_retries_when_first_task_prompt_does_not_reach_codex_transcript(
        self,
    ) -> None:
        instruction_path, _ = self.write_dispatch("codex")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "startup-blocked-codex-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AGENT_KIND": "codex",
                "HERDR_OMIT_AGENT_SESSION": "1",
                "HERDR_TRANSCRIPT_DELIVER_AFTER_PROMPTS": "2",
                "HERDR_TRANSCRIPT_NOISE": "MCP startup incomplete. Usage limits notice.",
            },
            timeout_seconds=20,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompts = [
            call
            for call in calls
            if call[:3] == ["agent", "prompt", "worker-pane"]
        ]
        self.assertEqual(len(prompts), 2)
        reads = [call for call in calls if call[:3] == ["agent", "read", "worker-pane"]]
        self.assertTrue(reads)
        self.assertIn("--source", reads[0])
        self.assertEqual(reads[0][reads[0].index("--source") + 1], "visible")

    def test_launcher_uses_a_bounded_start_prompt_for_a_long_task(self) -> None:
        instruction_path, _ = self.write_dispatch("codex")
        instruction = json.loads(instruction_path.read_text())
        task = "外層邊界可拖曳調寬，完成後驗證真實介面。" * 180
        instruction["task"] = task
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "long-task-codex-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AGENT_KIND": "codex",
                "HERDR_OMIT_AGENT_SESSION": "1",
                "HERDR_TRANSCRIPT_TAIL_CHARS": "256",
            },
            timeout_seconds=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompts = [
            call
            for call in calls
            if call[:3] == ["agent", "prompt", "worker-pane"]
        ]
        self.assertEqual(len(prompts), 1)
        digest = base64.urlsafe_b64encode(hashlib.sha256(task.encode()).digest()).decode().rstrip("=")
        self.assertEqual(
            prompts[0][3],
            "Begin contract task.\n"
            f"[sb256:{digest}]",
        )
        self.assertNotIn(task, prompts[0][3])
        self.assertLess(len(prompts[0][3]), 256)
        self.assertGreater(len(task), 256)

    def test_launcher_confirms_delivery_in_an_extremely_narrow_claude_viewport(
        self,
    ) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        instruction["task"] = "Implement the API contract from the database facts." * 40
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "narrow-claude-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AGENT_KIND": "claude",
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_TRANSCRIPT_RENDER_COLUMNS": "11",
                "HERDR_TRANSCRIPT_VISIBLE_LINES": "6",
            },
            timeout_seconds=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompts = [
            call
            for call in calls
            if call[:3] == ["agent", "prompt", "worker-pane"]
        ]
        self.assertEqual(len(prompts), 1)

    def test_transcript_matching_ignores_whitespace_inserted_inside_cjk_text(
        self,
    ) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from dispatch_transport import transcript_contains; "
                    "raise SystemExit(0 if transcript_contains("
                    "'外 層邊界可拖曳調寬', '外層邊界可拖曳調寬') else 1)"
                ),
            ],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(SCRIPTS)},
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_launcher_refuses_receipt_when_both_task_prompts_miss_transcript(
        self,
    ) -> None:
        instruction_path, _ = self.write_dispatch("codex")
        fake_bin, capture = self.install_fake_herdr()
        receipt_path = instruction_path.with_name("api--contract-codex.launch.json")

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "unreachable-codex-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AGENT_KIND": "codex",
                "HERDR_OMIT_AGENT_SESSION": "1",
                "HERDR_TRANSCRIPT_DELIVER_AFTER_PROMPTS": "3",
                "HERDR_TRANSCRIPT_NOISE": "MCP startup incomplete. Usage limits notice.",
            },
            timeout_seconds=30,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not confirm it landed in the transcript", result.stderr)
        self.assertFalse(receipt_path.exists())
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompts = [call for call in calls if call[:3] == ["agent", "prompt", "worker-pane"]]
        self.assertEqual(len(prompts), 2)
        self.assertIn(["pane", "close", "worker-pane"], calls)

    def test_launcher_applies_codex_profile_model_and_effort(self) -> None:
        instruction_path, _ = self.write_dispatch(
            "codex",
            agent_profile="docs",
            agent_model="gpt-5.6-sol",
            agent_effort="high",
        )
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "codex-docs",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": "codex-live-session",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        start = next(call for call in calls if call[:2] == ["agent", "start"])
        self.assertEqual(start.count("--profile"), 1)
        self.assertEqual(start[start.index("--profile") + 1], "docs")
        self.assertEqual(start.count("--model"), 1)
        self.assertEqual(start[start.index("--model") + 1], "gpt-5.6-sol")
        effort = "model_reasoning_effort=high"
        self.assertEqual(start.count(effort), 1)
        self.assertNotIn("--advisor", start)

    def test_launcher_accepts_older_instruction_without_profile_or_advisor(self) -> None:
        instruction_path, _ = self.write_dispatch("claude", agent_model="sonnet")
        instruction = json.loads(instruction_path.read_text())
        instruction.pop("agent_profile")
        instruction.pop("advisor_model")
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "older-instruction",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        start = next(call for call in calls if call[:2] == ["agent", "start"])
        self.assertNotIn("--agent", start)
        self.assertNotIn("--advisor", start)

    def test_launcher_rejects_raw_override_of_instruction_owned_model(self) -> None:
        instruction_path, _ = self.write_dispatch("claude", agent_model="sonnet")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "duplicate-model",
            "--agent-arg=--model",
            "--agent-arg=opus",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--model", result.stderr)
        if capture.exists():
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            self.assertFalse(any(call[:2] == ["pane", "split"] for call in calls))

    def test_launcher_rejects_and_closes_a_worker_pane_in_another_tab(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "api-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_MAIN_TAB_ID": "main-tab",
                "HERDR_WORKER_TAB_ID": "wrong-tab",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected main-agent tab", result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertIn(["pane", "close", "worker-pane"], calls)
        self.assertFalse(any(call[:2] == ["agent", "start"] for call in calls))
        receipt_path = instruction_path.with_name("api--contract-claude.launch.json")
        self.assertFalse(receipt_path.exists())

    def test_confirm_requires_a_matching_launch_receipt(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())

        missing = self.run_script(
            "dispatch-task.py",
            "confirm",
            "--app",
            "api",
            "--slug",
            "contract-claude",
            "--pane-id",
            "worker-pane",
            "--observed-session-id",
            str(instruction["session_id"]),
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("launch receipt", missing.stderr)
        self.assertEqual(json.loads(instruction_path.read_text())["status"], "pending")


if __name__ == "__main__":
    unittest.main()
