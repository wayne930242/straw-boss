#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Detached: clear a renewing pane after its turn ends, then start the next turn.

The follow-up prompt makes providers that run SessionStart lazily (Codex,
Antigravity) inject the record, and lets every provider continue the recorded
next action without the user restating it.

One deliverer serves a pane: a record rewritten before the clear is delivered by
the deliverer already waiting there, so the pane clears once.
"""

from __future__ import annotations

import argparse
import fcntl
import subprocess
import sys

from straw_boss.renewal import CLEAR_COMMAND, CONTINUE_PROMPT, record_key, record_path, load_record, renewal_root


TURN_END_TIMEOUT_MS = 30 * 60 * 1000
CLEAR_SETTLE_TIMEOUT_MS = 60 * 1000


def herdr(*args: str) -> int:
    return subprocess.run(["herdr", *args], capture_output=True, text=True).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pane-id", required=True)
    pane = parser.parse_args().pane_id
    lock_path = renewal_root() / f"{record_key(pane, None, '')}.deliver.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = lock_path.open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    if herdr("agent", "wait", pane, "--until", "idle", "--until", "done",
             "--timeout", str(TURN_END_TIMEOUT_MS)) != 0:
        return 1
    path = record_path(record_key(pane, None, ""))
    record = load_record(path)
    if record and record.get("jev_request"):
        from straw_boss.jev_codex_renewal import deliver, RenewalInterrupted
        try:
            if deliver(path):
                return 0
        except RenewalInterrupted:
            return 1
        except Exception as error:
            # A changed session/record owns new work; leave its pane intact.
            print(f"Jev renewal interrupted: {type(error).__name__}.", file=sys.stderr)
            from straw_boss.jev_codex_transport import live_agent, session_value
            current = load_record(path)
            try:
                agent = live_agent(pane)
            except (ValueError, OSError):
                return 1
            if not (current and current.get("status") == "pending"
                    and current.get("session_id") == record.get("session_id")
                    and current.get("jev_request") == record.get("jev_request")
                    and session_value(agent) == current.get("session_id")
                    and agent.get("agent_status") in {"idle", "done"}):
                return 1
    if herdr("agent", "prompt", pane, CLEAR_COMMAND) != 0:
        return 1
    herdr("agent", "wait", pane, "--until", "idle", "--until", "done",
          "--timeout", str(CLEAR_SETTLE_TIMEOUT_MS))
    return herdr("agent", "prompt", pane, CONTINUE_PROMPT)


if __name__ == "__main__":
    raise SystemExit(main())
