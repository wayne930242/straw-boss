#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Claude PreToolUse hook: keep subagents off Straw Boss dispatch channels.

A subagent -- a fork above all, which inherits the whole conversation and
with it the dispatched-agent contract -- runs in its parent's pane with the
parent's session id and environment, so a channel script cannot tell its
calls from the parent's. Its reports and questions then reach the main agent
and the parent as though another agent held the same dispatch. The hook
input's `agent_id` is present only for a subagent's tool calls, so that is
where the call is refused.
"""

from __future__ import annotations

import json
import re
import sys


# A channel script counts where a launcher runs it -- after uv run, python,
# or exec, or as a --script value -- so reading or grepping one stays open.
CHANNEL_INVOCATION = re.compile(
    r"""(?:
          \b(?:python3?|exec|uv\s+run(?:\s+-[\w-]+(?:\s+[^-\s]\S*)?)*?)\s+
        | --script(?:=|\s+)
        )["']?(?:[^\s"';&|]*/)?
        (?:run-straw-boss-script|report-progress|report-task-status|send-dispatch-message)\.py\b""",
    re.VERBOSE,
)
REASON = (
    "Straw Boss dispatch channels speak for this pane's own session, and you are a "
    "subagent of it. Return your result to the agent that spawned you; it reports "
    "progress and status, and asks the main agent, itself."
)


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = (hook_input.get("tool_input") or {}).get("command")
    if not hook_input.get("agent_id") or not isinstance(command, str):
        return 0
    if CHANNEL_INVOCATION.search(command):
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": REASON,
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
