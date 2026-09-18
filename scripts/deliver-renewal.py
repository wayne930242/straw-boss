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

from straw_boss.renewal import CLEAR_COMMAND, CONTINUE_PROMPT, record_key, renewal_root


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
    if herdr("agent", "prompt", pane, CLEAR_COMMAND) != 0:
        return 1
    herdr("agent", "wait", pane, "--until", "idle", "--until", "done",
          "--timeout", str(CLEAR_SETTLE_TIMEOUT_MS))
    return herdr("agent", "prompt", pane, CONTINUE_PROMPT)


if __name__ == "__main__":
    raise SystemExit(main())
