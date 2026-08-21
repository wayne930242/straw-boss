#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""SessionStart hook: primes a candidate main-agent session with the
i-am-orchestrator skill's own operating stance, guaranteed rather than
left to the model choosing to invoke that skill itself.

Skipped for a dispatched worker session -- detected by checking whether
this session's own session_id (from the hook's stdin payload) matches a
session_id already recorded in a dispatch instruction file.
dispatch-task.py write pre-generates and passes that session_id via
--session-id at launch (both dispatch modes -- see
skills/dispatching-work/references/dispatch-mechanics.md), so a worker's
own session_id is always found there; a worker must never be primed as
if it were the orchestrator.

Registered via hooks/hooks.json (SessionStart, matcher "*" -- fires on
startup/resume/clear/compact/fork alike, so a compacted main-agent
session gets re-primed too, not just a fresh one).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def mp_dev_root() -> Path:
    return Path.home() / ".straw-boss"


def is_dispatched_worker(session_id: str) -> bool:
    dispatch_dir = mp_dev_root() / "dispatch"
    for pattern in ("*.json", "archive/*.json"):
        for path in dispatch_dir.glob(pattern):
            try:
                payload = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get("session_id") == session_id:
                return True
    return False


def orchestrator_stance() -> str:
    skill_path = Path(__file__).resolve().parent.parent / "skills" / "i-am-orchestrator" / "SKILL.md"
    text = skill_path.read_text()
    if text.startswith("---"):
        _, _, text = text.partition("---\n")
        _, _, text = text.partition("---\n")
    return text.strip()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # never block session start over a malformed hook payload

    session_id = payload.get("session_id")
    if session_id and is_dispatched_worker(session_id):
        return 0

    print(orchestrator_stance())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
