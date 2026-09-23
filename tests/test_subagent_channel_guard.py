"""A subagent shares its parent's pane and session, so only the Claude hook's
agent_id can tell its tool calls apart; it must not speak on dispatch channels."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "subagent-channel-guard.py"
INSTRUCTION = "/home/.straw-boss/dispatch/app--slug.json"
# The fork's own call from friction report 394969c2, as the contract renders it.
LAUNCHER_CALL = (
    "uv run --script /home/.straw-boss/bin/run-straw-boss-script.py "
    "--origin-root /home/.claude/plugins/cache/straw-boss/straw-boss/0.30.38 --prefer-installed "
    f"--script report-task-status.py -- --instruction-path {INSTRUCTION} "
    "--status awaiting-main-agent --note 'Pausing implementation'"
)
DIRECT_CALL = (
    'uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" '
    f"--instruction-path {INSTRUCTION} --to main --intent question --message 'Which of us continues?'"
)


def hook_input(command: str, **fields: str) -> dict:
    return {
        "session_id": "worker-session",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        **fields,
    }


class SubagentChannelGuardTest(unittest.TestCase):
    def run_guard(self, payload: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GUARD)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=10,
        )

    def assert_denied(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("spawned you", output["permissionDecisionReason"])

    def assert_allowed(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_subagent_channel_calls_are_denied(self):
        for command in (
            LAUNCHER_CALL,
            DIRECT_CALL,
            f"uv run scripts/report-task-status.py --instruction-path {INSTRUCTION} --status done",
            f'python3 "$ROOT/scripts/report-progress.py" --instruction-path {INSTRUCTION} --note x',
            f"cd /repo && exec scripts/send-dispatch-message.py --instruction-path {INSTRUCTION}",
        ):
            with self.subTest(command=command):
                self.assert_denied(
                    self.run_guard(hook_input(command, agent_id="a1982cac36696c692", agent_type="fork"))
                )

    def test_main_thread_channel_calls_pass(self):
        # An --agent session carries agent_type on its main thread, never agent_id.
        for fields in ({}, {"agent_type": "worker"}):
            for command in (LAUNCHER_CALL, DIRECT_CALL):
                with self.subTest(fields=fields, command=command):
                    self.assert_allowed(self.run_guard(hook_input(command, **fields)))

    def test_subagent_reading_channel_scripts_passes(self):
        for command in (
            "sed -n 1,40p scripts/report-progress.py",
            "grep -rn 'run-straw-boss-script.py' skills",
            'grep -rn -- "--script.*report-progress.py" skills/',
            'grep -rn "report-task-status.py\\|report-progress.py" skills',
            "git commit -F - <<'MSG'\nfix: guard channels\n\nsend-dispatch-message.py\nMSG",
            "uv run --with pytest pytest -q tests/test_report_progress.py",
        ):
            with self.subTest(command=command):
                self.assert_allowed(self.run_guard(hook_input(command, agent_id="a1", agent_type="Explore")))

    def test_claude_manifest_runs_the_guard_for_bash(self):
        claude = json.loads((ROOT / "hooks/hooks.json").read_text())
        [entry] = claude["hooks"]["PreToolUse"]
        self.assertEqual(entry["matcher"], "Bash")
        [hook] = entry["hooks"]
        result = subprocess.run(
            hook["command"],
            shell=True,
            input=json.dumps(hook_input(LAUNCHER_CALL, agent_id="a1", agent_type="fork")),
            env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(ROOT)},
            cwd="/",
            capture_output=True,
            text=True,
            timeout=hook["timeout"],
        )
        self.assert_denied(result)


if __name__ == "__main__":
    unittest.main()
