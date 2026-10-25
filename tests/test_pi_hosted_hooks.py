"""Pi drives Claude Code through the Agent SDK (pi-claude-bridge), and a bridge
that loads the user's settings loads this plugin's hooks too. Pi owns that
session, so every hook stays silent there, while a claude CLI keeps them."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import ROOT, SCRIPTS, DispatchedAgentLifecycleFixture

PI_SDK_CHILD = {"PI_CODING_AGENT": "true", "CLAUDE_CODE_ENTRYPOINT": "sdk-ts"}
SUBAGENT_CHANNEL_CALL = (
    'uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" '
    "--instruction-path /home/.straw-boss/dispatch/app--slug.json --to main --intent question --message 'Which?'"
)


class PiHostedHookTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def hook(self, script: str, payload: dict[str, Any], **extra: str) -> str:
        env = {**os.environ, "HOME": str(self.home)}
        for name in ("PI_CODING_AGENT", "CLAUDE_CODE_ENTRYPOINT", "HERDR_PANE_ID"):
            env.pop(name, None)
        env.update(extra)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / script)],
            input=json.dumps(payload),
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def large_turn(self) -> dict[str, Any]:
        transcript = self.home / "claude.jsonl"
        usage = {"input_tokens": 10, "cache_read_input_tokens": 249_980, "cache_creation_input_tokens": 10}
        transcript.write_text(json.dumps({"type": "assistant", "message": {"usage": usage}}) + "\n")
        return {"session_id": "s1", "transcript_path": str(transcript)}

    def test_context_renewal_stays_silent_under_pi(self) -> None:
        payload = self.large_turn()
        self.assertEqual(json.loads(self.hook("context-renewal-guard.py", payload))["decision"], "block")
        self.assertEqual(self.hook("context-renewal-guard.py", payload, **PI_SDK_CHILD), "")

    def test_a_claude_cli_that_inherited_pi_environment_keeps_its_hooks(self) -> None:
        stdout = self.hook("context-renewal-guard.py", self.large_turn(),
                           PI_CODING_AGENT="true", CLAUDE_CODE_ENTRYPOINT="cli")
        self.assertEqual(json.loads(stdout)["decision"], "block")

    def test_dispatched_stop_guard_stays_silent_under_pi(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        instruction["status"] = "in-progress"
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")
        payload = {"session_id": instruction["session_id"]}
        self.assertEqual(json.loads(self.hook("dispatched-agent-stop-guard.py", payload))["decision"], "block")
        self.assertEqual(self.hook("dispatched-agent-stop-guard.py", payload, **PI_SDK_CHILD), "")

    def test_priming_stays_silent_under_pi(self) -> None:
        payload = {"session_id": "main-session", "source": "startup"}
        self.assertIn("orchestrator", self.hook("orchestrator-priming.py", payload).lower())
        self.assertEqual(self.hook("orchestrator-priming.py", payload, **PI_SDK_CHILD), "")

    def test_subagent_channel_guard_stays_silent_under_pi(self) -> None:
        payload = {
            "session_id": "worker-session",
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": SUBAGENT_CHANNEL_CALL},
            "agent_id": "fork-1",
        }
        denied = json.loads(self.hook("subagent-channel-guard.py", payload))
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.hook("subagent-channel-guard.py", payload, **PI_SDK_CHILD), "")


if __name__ == "__main__":
    unittest.main()
