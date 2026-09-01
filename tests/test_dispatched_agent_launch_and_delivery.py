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
                # Pin the attempt schedule so this stays a test about delivery
                # confirmation rather than about the production retry budget.
                "STRAW_BOSS_PROMPT_RETRY_BACKOFF_SECONDS": "0,0",
            },
            timeout_seconds=30,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not confirm it landed in the transcript", result.stderr)
        self.assertFalse(receipt_path.exists())
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompts = [call for call in calls if call[:3] == ["agent", "prompt", "worker-pane"]]
        self.assertEqual(len(prompts), 2)
        self.assertNotIn(["pane", "close", "worker-pane"], calls)
        self.assertIn("is left open", result.stderr)

    def test_launcher_refuses_receipt_when_task_prompt_only_reaches_the_composer(
        self,
    ) -> None:
        # herdr can write the prompt text into an idle agent's composer
        # without ever starting a turn. The old substring-only transcript
        # check cannot tell that apart from a real delivery -- confirmation
        # must also use herdr's own --wait/agent_prompt_stalled lifecycle
        # gate (see `herdr agent prompt --help` on this machine's herdr 0.8.0).
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()
        receipt_path = instruction_path.with_name("api--contract-claude.launch.json")

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "composer-only-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_PROMPT_WAIT_ERROR_CODES": json.dumps(
                    {"worker-pane": "agent_prompt_stalled"}
                ),
                "STRAW_BOSS_PROMPT_RETRY_BACKOFF_SECONDS": "0,0",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("agent_prompt_stalled", result.stderr)
        self.assertFalse(receipt_path.exists())
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompts = [call for call in calls if call[:3] == ["agent", "prompt", "worker-pane"]]
        self.assertEqual(len(prompts), 2)
        self.assertTrue(all("--wait" in call for call in prompts))
        # The composer-only prompt is still captured (visible on screen);
        # only herdr's lifecycle gate, not transcript visibility, catches it.
        self.assertIn("sb256:", prompts[0][3])
        # The agent booted fine and only the opening handoff missed, so the pane
        # stays up for a retry instead of being torn down with the agent in it.
        self.assertNotIn(["pane", "close", "worker-pane"], calls)
        self.assertIn("is left open", result.stderr)

    def test_launcher_refuses_receipt_when_a_persistently_blocked_worker_only_reaches_the_composer(
        self,
    ) -> None:
        # A worker still blocked on a (possibly fresh) permission prompt
        # after the launcher's own enter+wait recovery reaches
        # prompt_task_with_confirmation with pre-send status "blocked" --
        # herdr's --wait gate must still apply there, since blocked is a
        # non-working state, not fall back to composer-only-vulnerable
        # plain submission just because it isn't idle.
        instruction_path, _ = self.write_dispatch("codex")
        fake_bin, capture = self.install_fake_herdr()
        receipt_path = instruction_path.with_name("api--contract-codex.launch.json")

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "persistently-blocked-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AGENT_STATUSES": json.dumps({"worker-pane": "blocked"}),
                "HERDR_PROMPT_WAIT_ERROR_CODES": json.dumps(
                    {"worker-pane": "agent_prompt_stalled"}
                ),
                "STRAW_BOSS_PROMPT_RETRY_BACKOFF_SECONDS": "0,0",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("agent_prompt_stalled", result.stderr)
        self.assertFalse(receipt_path.exists())
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompts = [call for call in calls if call[:3] == ["agent", "prompt", "worker-pane"]]
        self.assertEqual(len(prompts), 2)
        self.assertTrue(all("--wait" in call for call in prompts))
        self.assertNotIn(["pane", "close", "worker-pane"], calls)
        self.assertIn("is left open", result.stderr)

    def test_launcher_reports_a_claude_startup_gate_instead_of_submitting_into_it(
        self,
    ) -> None:
        # The failure this exists for: a first-run gate (folder trust) leaves a
        # Claude worker blocked before its first turn with "No, exit"
        # preselected, so the opening prompt -- or a blind enter -- exits the
        # worker herdr had just reported healthy. The gate is named, the pane
        # is kept for whoever answers it, and nothing is retried into it.
        instruction_path, _ = self.write_dispatch("claude")
        fake_bin, capture = self.install_fake_herdr()
        receipt_path = instruction_path.with_name("api--contract-claude.launch.json")
        failure_path = instruction_path.with_name(
            "api--contract-claude.launch-failure.json"
        )

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "trust-gated-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AGENT_STATUSES": json.dumps({"worker-pane": "blocked"}),
                "HERDR_PANE_TEXT": "Is this a project you created or one you trust?\n"
                " > No, exit\n   Yes, I trust this folder",
                "STRAW_BOSS_LAUNCH_RETRY_BACKOFF_SECONDS": "0,0,0",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("startup gate", result.stderr)
        self.assertIn("Yes, I trust this folder", result.stderr)
        self.assertFalse(receipt_path.exists())
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertFalse([call for call in calls if call[:2] == ["agent", "prompt"]])
        self.assertFalse([call for call in calls if call[:2] == ["agent", "send-keys"]])
        self.assertNotIn(["pane", "close", "worker-pane"], calls)
        self.assertEqual(len([c for c in calls if c[:2] == ["agent", "start"]]), 1)
        recorded = json.loads(failure_path.read_text())
        self.assertEqual(len(recorded["attempts"]), 1)
        self.assertFalse(recorded["attempts"][0]["retryable"])
        self.assertTrue(recorded["attempts"][0]["pane_left_open"])
        self.assertIn("No, exit", recorded["attempts"][0]["pane_excerpt"])

    def test_launcher_reads_a_startup_gate_off_the_pane_when_herdr_still_says_idle(
        self,
    ) -> None:
        # herdr classifies a fresh trust gate as blocked about a second after
        # `agent start` returns, so a launch that trusts the status alone can
        # still submit into a gate herdr is calling idle. The gate's own
        # preselected option on the pane is the second, independent signal.
        instruction_path, _ = self.write_dispatch("claude")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "idle-looking-gated-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AGENT_STATUSES": json.dumps({"worker-pane": "idle"}),
                # As a narrow worker pane renders it: the option wraps away
                # from its own bullet.
                "HERDR_PANE_TEXT": " Security guide\n\n \u276f No,\n exit\n   Yes, I trust\n   this folder",
                "STRAW_BOSS_LAUNCH_RETRY_BACKOFF_SECONDS": "0,0,0",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("startup gate", result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertFalse([call for call in calls if call[:2] == ["agent", "prompt"]])
        self.assertNotIn(["pane", "close", "worker-pane"], calls)

    def test_launcher_retries_a_worker_that_vanishes_and_records_why_when_it_gives_up(
        self,
    ) -> None:
        # An agent that goes away mid-launch is the one shape a second attempt
        # can clear, so it is retried with a fresh session id rather than
        # handed back for the coordinator to rerun by hand -- and when the
        # bounded retries run out the reason lands beside the instruction
        # instead of only on stderr.
        instruction_path, _ = self.write_dispatch("claude")
        first_session = json.loads(instruction_path.read_text())["session_id"]
        fake_bin, capture = self.install_fake_herdr()
        failure_path = instruction_path.with_name(
            "api--contract-claude.launch-failure.json"
        )

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "vanishing-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_PANE_TEXT": "Error: Session ID is already in use.",
                "HERDR_PROMPT_WAIT_ERROR_CODES": json.dumps(
                    {"worker-pane": "agent_not_running"}
                ),
                "STRAW_BOSS_LAUNCH_RETRY_BACKOFF_SECONDS": "0,0,0",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("launch failed after 3 attempt(s)", result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        starts = [call for call in calls if call[:2] == ["agent", "start"]]
        self.assertEqual(len(starts), 3)
        self.assertEqual(
            len([call for call in calls if call[:2] == ["pane", "close"]]), 3
        )
        recorded = json.loads(failure_path.read_text())
        self.assertEqual(len(recorded["attempts"]), 3)
        self.assertTrue(all(a["retryable"] for a in recorded["attempts"]))
        self.assertIn("Session ID is already in use", recorded["attempts"][0]["pane_excerpt"])
        session_ids = [a["session_id"] for a in recorded["attempts"]]
        self.assertEqual(session_ids[0], first_session)
        self.assertEqual(len(set(session_ids)), 3)

    def test_launcher_keeps_the_pane_when_bookkeeping_fails_after_confirmed_delivery(
        self,
    ) -> None:
        # Once the task is confirmed in the worker's transcript the worker is
        # doing the job, and the remaining identity checks are this launcher's
        # own bookkeeping. Closing that pane destroys a working agent for a
        # reason that has nothing to do with it -- the same principle the
        # missed-handoff path already follows.
        instruction_path, _ = self.write_dispatch("claude")
        fake_bin, capture = self.install_fake_herdr()
        failure_path = instruction_path.with_name(
            "api--contract-claude.launch-failure.json"
        )

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "delivered-but-unrecorded-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": "somebody-elses-session",
                "STRAW_BOSS_LAUNCH_RETRY_BACKOFF_SECONDS": "0,0,0",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already confirmed delivered", result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertNotIn(["pane", "close", "worker-pane"], calls)
        self.assertEqual(len([c for c in calls if c[:2] == ["agent", "start"]]), 1)
        recorded = json.loads(failure_path.read_text())
        self.assertEqual(len(recorded["attempts"]), 1)
        self.assertTrue(recorded["attempts"][0]["pane_left_open"])

    def test_launcher_records_the_trail_after_each_failed_attempt_not_only_at_the_end(
        self,
    ) -> None:
        # A run killed mid-retry must still leave the trail this file exists to
        # guarantee, and the spent session ids accumulate across runs even
        # though each run rewrites the attempt list.
        instruction_path, _ = self.write_dispatch("claude")
        first_session = json.loads(instruction_path.read_text())["session_id"]
        failure_path = instruction_path.with_name(
            "api--contract-claude.launch-failure.json"
        )
        failure_path.write_text(
            json.dumps({"spent_session_ids": ["an-id-from-a-much-earlier-run"]})
        )
        fake_bin, capture = self.install_fake_herdr()

        self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "trail-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_PROMPT_WAIT_ERROR_CODES": json.dumps(
                    {"worker-pane": "agent_not_running"}
                ),
                "STRAW_BOSS_LAUNCH_RETRY_BACKOFF_SECONDS": "0,0,0",
            },
        )

        recorded = json.loads(failure_path.read_text())
        self.assertEqual(len(recorded["attempts"]), 3)
        self.assertIn("an-id-from-a-much-earlier-run", recorded["spent_session_ids"])
        self.assertIn(first_session, recorded["spent_session_ids"])
        self.assertEqual(len(recorded["spent_session_ids"]), 4)

    def test_launcher_starts_a_rerun_on_a_session_id_no_earlier_attempt_spent(
        self,
    ) -> None:
        # `claude --session-id` refuses an id it has already seen, so a rerun
        # that reuses the id an earlier run already handed to a booted agent
        # would die at startup every time. The recorded attempt trail is what
        # makes that knowable across processes.
        instruction_path, _ = self.write_dispatch("claude")
        spent = json.loads(instruction_path.read_text())["session_id"]
        instruction_path.with_name("api--contract-claude.launch-failure.json").write_text(
            json.dumps({"attempts": [{"attempt": 1, "session_id": spent}]})
        )
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "rerun-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_SESSION_FROM_START": "1",
                "STRAW_BOSS_LAUNCH_RETRY_BACKOFF_SECONDS": "0,0,0",
            },
        )

        rotated = json.loads(instruction_path.read_text())["session_id"]
        self.assertNotEqual(rotated, spent)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        starts = [call for call in calls if call[:2] == ["agent", "start"]]
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0][starts[0].index("--session-id") + 1], rotated)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_launcher_does_not_resend_on_an_ambiguous_prompt_wait_failure(
        self,
    ) -> None:
        # A plain herdr --wait timeout is ambiguous (the turn may or may not
        # have started) -- unlike a confirmed agent_prompt_stalled, it must
        # not trigger a second prompt, or a genuinely-delivered task could be
        # duplicated into the agent's composer.
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()
        receipt_path = instruction_path.with_name("api--contract-claude.launch.json")

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "ambiguous-wait-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_PROMPT_WAIT_ERROR_CODES": json.dumps({"worker-pane": "timeout"}),
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timeout", result.stderr)
        self.assertFalse(receipt_path.exists())
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompts = [call for call in calls if call[:3] == ["agent", "prompt", "worker-pane"]]
        self.assertEqual(len(prompts), 1)
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
