from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class DispatchedAgentLifecycleTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        (self.home / ".straw-boss" / "dispatch").mkdir(parents=True)

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

    def write_dispatch(self, agent_kind: str = "claude") -> tuple[Path, dict[str, object]]:
        result = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            f"contract-{agent_kind}",
            "--task",
            "Implement the requested slice and verify it.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(ROOT),
            "--agent-kind",
            agent_kind,
            "--main-agent-kind",
            "codex",
            "--main-agent-pane-id",
            "main-pane",
            "--main-agent-session-id",
            "main-session",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        return Path(output["instruction_path"]), output

    def install_fake_herdr(self) -> tuple[Path, Path]:
        fake_bin = self.home / "bin"
        fake_bin.mkdir(exist_ok=True)
        capture = self.home / "herdr-calls.jsonl"
        fake_herdr = fake_bin / "herdr"
        fake_herdr.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "with open(os.environ['HERDR_CAPTURE'], 'a') as f:\n"
            "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "args = sys.argv[1:]\n"
            "if args[:2] == ['agent', 'get']:\n"
            "    target = args[2]\n"
            "    sessions = json.loads(os.environ.get('HERDR_SESSIONS', '{}'))\n"
            "    session = sessions.get(target, os.environ.get('HERDR_LIVE_SESSION', 'worker-session'))\n"
            "    print(json.dumps({'result': {'agent': {'name': 'worker', 'agent_status': 'idle', 'agent_session': {'value': session}}}}))\n"
            "else:\n"
            "    print(json.dumps({'result': {'agent': {'name': 'worker', 'agent_status': 'idle'}}}))\n"
        )
        fake_herdr.chmod(0o755)
        return fake_bin, capture

    def test_write_generates_a_hashed_system_contract_before_launch(self) -> None:
        instruction_path, output = self.write_dispatch("claude")

        instruction = json.loads(instruction_path.read_text())
        contract_path = Path(str(output["contract_path"]))
        self.assertTrue(contract_path.is_file())
        self.assertEqual(instruction["contract_path"], str(contract_path))
        self.assertRegex(str(instruction["contract_sha256"]), r"^[0-9a-f]{64}$")
        self.assertEqual(instruction["main_agent_session_id"], "main-session")

        contract = contract_path.read_text()
        self.assertIn(str(instruction_path), contract)
        self.assertIn("report-task-status.py", contract)
        self.assertIn("awaiting-user-input", contract)
        self.assertIn("awaiting-main-agent", contract)
        self.assertIn("awaiting-authorization", contract)
        self.assertIn("Before stopping", contract)
        self.assertIn("Do not use SendMessage", contract)

    def test_task_authoring_guidance_prioritizes_outcome_and_context(self) -> None:
        shipping = (ROOT / "skills" / "shipping-task" / "SKILL.md").read_text()
        plan_mechanics = (
            ROOT / "skills" / "dispatching-work" / "references" / "plan-mechanics.md"
        ).read_text()

        for source in (shipping, plan_mechanics):
            self.assertIn("clear requested outcome", source)
            self.assertIn("sufficient verified context", source)
            self.assertIn("possible implementation", source)
            self.assertIn("generic lifecycle prose", source)

        self.assertNotIn(
            "selected lifecycle/worktree, mutation gates, tracker boundary, checkpoints",
            shipping,
        )
        self.assertNotIn(
            "Task-specific prose adds only tracker boundaries",
            plan_mechanics,
        )

    def test_herdr_dispatch_requires_main_agent_session_fingerprint(self) -> None:
        result = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            "missing-main-session",
            "--task",
            "Run the task.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(ROOT),
            "--agent-kind",
            "claude",
            "--main-agent-kind",
            "codex",
            "--main-agent-pane-id",
            "main-pane",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--main-agent-session-id is required", result.stderr)

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
            "--pane-id",
            "worker-pane",
            "--tab-id",
            "tab-1",
            extra_env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        calls = [json.loads(line) for line in capture.read_text().splitlines()]
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

    def test_launcher_injects_codex_developer_instructions(self) -> None:
        instruction_path, _ = self.write_dispatch("codex")
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
            "--pane-id",
            "worker-pane",
            extra_env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        public_result = json.loads(result.stdout)
        self.assertNotIn("target_session_id", public_result)
        self.assertNotIn("pane_id", public_result)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        start = next(call for call in calls if call[:2] == ["agent", "start"])
        config_index = start.index("-c")
        self.assertTrue(start[config_index + 1].startswith("developer_instructions="))
        self.assertIn("report-task-status.py", start[config_index + 1])

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

    def test_script_routes_to_main_by_instruction_and_validates_live_session(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        fake_bin, capture = self.install_fake_herdr()
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_SESSIONS": json.dumps({"main-pane": "main-session"}),
        }

        result = self.run_script(
            "send-dispatch-message.py",
            "--instruction-path",
            str(instruction_path),
            "--to",
            "main",
            "--intent",
            "question",
            "--message",
            "Which boundary should I preserve?",
            extra_env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        public_result = json.loads(result.stdout)
        self.assertNotIn("target_session_id", public_result)
        self.assertNotIn("pane_id", public_result)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(calls[0], ["agent", "get", "main-pane"])
        self.assertEqual(calls[1][:3], ["agent", "prompt", "main-pane"])
        self.assertIn("Which boundary should I preserve?", calls[1][3])

    def test_transport_refuses_reused_coordinator_pane_before_prompting(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        fake_bin, capture = self.install_fake_herdr()
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_SESSIONS": json.dumps({"main-pane": "different-session"}),
        }

        result = self.run_script(
            "send-dispatch-message.py",
            "--instruction-path",
            str(instruction_path),
            "--to",
            "main",
            "--intent",
            "status",
            "--message",
            "done",
            extra_env=env,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("session mismatch", result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(calls, [["agent", "get", "main-pane"]])

    def test_script_routes_to_worker_without_caller_supplied_endpoint(self) -> None:
        instruction_path, _ = self.write_dispatch("codex")
        instruction = json.loads(instruction_path.read_text())
        instruction["status"] = "in-progress"
        instruction["herdr_pane_id"] = "worker-pane"
        instruction["session_id"] = "worker-session"
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")
        fake_bin, capture = self.install_fake_herdr()
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_SESSIONS": json.dumps({"worker-pane": "worker-session"}),
        }

        result = self.run_script(
            "send-dispatch-message.py",
            "--instruction-path",
            str(instruction_path),
            "--to",
            "worker",
            "--intent",
            "inform",
            "--message",
            "The dependency is now available.",
            extra_env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(calls[0], ["agent", "get", "worker-pane"])
        self.assertEqual(calls[1][:3], ["agent", "prompt", "worker-pane"])

    def test_status_is_written_before_session_validated_notification(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        fake_bin = self.home / "ordered-bin"
        fake_bin.mkdir()
        fake_herdr = fake_bin / "herdr"
        status_path = instruction_path.with_name("api--contract-claude.status.json")
        fake_herdr.write_text(
            "#!/bin/sh\n"
            "[ -f \"$EXPECTED_STATUS_PATH\" ] || exit 9\n"
            "if [ \"$2\" = get ]; then\n"
            "  printf '%s\\n' '{\"result\":{\"agent\":{\"agent_session\":{\"value\":\"main-session\"}}}}'\n"
            "else\n"
            "  printf '%s\\n' '{\"result\":{}}'\n"
            "fi\n"
        )
        fake_herdr.chmod(0o755)

        result = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "done",
            "--note",
            "verified",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "EXPECTED_STATUS_PATH": str(status_path),
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(status_path.read_text())["status"], "done")

    def test_stop_hook_blocks_a_dispatched_agent_without_a_status_report(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        instruction["status"] = "in-progress"
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "dispatched-agent-stop-guard.py")],
            input=json.dumps({"session_id": instruction["session_id"]}),
            cwd=ROOT,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["decision"], "block")
        self.assertIn(str(instruction_path), decision["reason"])
        self.assertIn("report-task-status.py", decision["reason"])

    def test_stop_hook_allows_a_dispatched_agent_after_a_valid_report(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        instruction["status"] = "in-progress"
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")
        status_path = instruction_path.with_name("api--contract-claude.status.json")
        status_path.write_text(
            json.dumps({"status": "done", "note": "verified", "timestamp": "now"})
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "dispatched-agent-stop-guard.py")],
            input=json.dumps({"session_id": instruction["session_id"]}),
            cwd=ROOT,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_hook_registration_includes_the_stop_guard(self) -> None:
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())
        commands = [
            hook["command"]
            for entry in hooks["hooks"]["Stop"]
            for hook in entry["hooks"]
        ]
        self.assertTrue(
            any("dispatched-agent-stop-guard.py" in command for command in commands)
        )

    def test_session_start_repeats_the_matching_worker_contract_on_resume(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "orchestrator-priming.py")],
            input=json.dumps({"session_id": instruction["session_id"]}),
            cwd=ROOT,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(instruction_path), result.stdout)
        self.assertIn("report-task-status.py", result.stdout)
        self.assertNotIn("orchestrator", result.stdout.lower())

    def test_control_message_preserves_the_exact_slash_command(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        instruction["status"] = "in-progress"
        instruction["herdr_pane_id"] = "worker-pane"
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")
        fake_bin, capture = self.install_fake_herdr()
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_SESSIONS": json.dumps(
                {"worker-pane": str(instruction["session_id"])}
            ),
        }

        result = self.run_script(
            "send-dispatch-message.py",
            "--instruction-path",
            str(instruction_path),
            "--to",
            "worker",
            "--intent",
            "control",
            "--message",
            "/compact preserve transport state",
            extra_env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(calls[1], ["agent", "prompt", "worker-pane", "/compact preserve transport state"])

    def test_wrap_up_archives_contract_receipt_and_delivery_ledger(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        stem = instruction_path.name.removesuffix(".json")
        status_path = instruction_path.with_name(f"{stem}.status.json")
        status_path.write_text(json.dumps({"status": "done"}) + "\n")
        launch_path = instruction_path.with_name(f"{stem}.launch.json")
        launch_path.write_text(json.dumps({"session_id": "worker"}) + "\n")
        messages_path = instruction_path.with_name(f"{stem}.messages.jsonl")
        messages_path.write_text(json.dumps({"intent": "status"}) + "\n")

        result = self.run_script(
            "wrap-up-task.py", "--app", "api", "--slug", "contract-claude"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        archive = self.home / ".straw-boss" / "dispatch" / "archive"
        for suffix in (".json", ".contract.md", ".launch.json", ".status.json", ".messages.jsonl"):
            self.assertTrue((archive / f"{stem}{suffix}").is_file(), suffix)

    def test_delivery_ledger_records_proof_without_duplicating_message_content(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        fake_bin, capture = self.install_fake_herdr()
        secret_message = "coordination detail that should not be duplicated"
        result = self.run_script(
            "send-dispatch-message.py",
            "--instruction-path",
            str(instruction_path),
            "--to",
            "main",
            "--intent",
            "inform",
            "--message",
            secret_message,
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_SESSIONS": json.dumps({"main-pane": "main-session"}),
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        ledger_path = instruction_path.with_name("api--contract-claude.messages.jsonl")
        record = json.loads(ledger_path.read_text())
        self.assertNotIn("message", record)
        self.assertEqual(record["message_length"], len(secret_message))
        self.assertRegex(record["message_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn(secret_message, ledger_path.read_text())

    def test_shared_resource_lock_records_instruction_path_not_raw_main_endpoint(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        result = self.run_script(
            "claim-resource.py",
            "acquire",
            "--resource",
            "db-migration--test",
            "--holder",
            "api--contract-claude",
            "--requester-instruction-path",
            str(instruction_path),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        lock = json.loads(
            (self.home / ".straw-boss" / "locks" / "db-migration--test.json").read_text()
        )
        self.assertEqual(lock["holder_instruction_path"], str(instruction_path))
        self.assertNotIn("holder_boss", lock)

    def test_active_skills_have_no_provider_native_cross_session_fallback(self) -> None:
        skill_text = "\n".join(
            path.read_text() for path in sorted((ROOT / "skills").rglob("*.md"))
        )
        self.assertNotIn("SendMessage", skill_text)
        self.assertFalse((SCRIPTS / "get-main-agent.py").exists())


if __name__ == "__main__":
    unittest.main()
