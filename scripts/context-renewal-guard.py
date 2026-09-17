#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Stop hook: a turn that ends above the renewal threshold renews its session.

The hook measures; the model writes the continuity record through
renew-context.py, which also schedules the clear. A second stop in the same
turn is let through, so a session that cannot renew is never trapped.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from straw_boss.renewal import (
    AGY_BLOCK_WINDOW_SECONDS,
    RENEWAL_THRESHOLD_TOKENS,
    ROLES,
    context_tokens,
    current_record_path,
    dump_json,
    load_record,
    payload_agent_kind,
    payload_session,
    pending_record_from,
    renewal_root,
)


def already_blocked_this_turn(payload: dict, agent_kind: str, session: str) -> bool:
    if agent_kind != "agy":
        return bool(payload.get("stop_hook_active"))
    marker = renewal_root() / "blocked" / session
    if marker.is_file() and time.time() - marker.stat().st_mtime < AGY_BLOCK_WINDOW_SECONDS:
        marker.unlink(missing_ok=True)
        return True
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    return False


def renewal_reason(agent_kind: str, session: str, tokens: int) -> str:
    script = Path(__file__).resolve().parent / "renew-context.py"
    return (
        f"Context renewal: this turn ended with {tokens} context tokens, above "
        f"{RENEWAL_THRESHOLD_TOKENS}. Renew now without asking the user. Pipe the continuity "
        "payload -- goal and scope, confirmed decisions and user terms, current state and "
        "evidence, next action, exclusions -- on stdin to: "
        f"uv run --script {script} --agent-kind {agent_kind} --session-id {session} "
        f"--role <{'|'.join(ROLES)}> [--instruction-path <dispatch you own or serve>]... "
        "Then print its one-line notice and end the turn."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    session = payload_session(payload)
    if not session:
        return 0
    agent_kind = payload_agent_kind(payload)
    path = current_record_path(payload, agent_kind)
    if pending_record_from(path, session):
        return 0
    tokens = context_tokens(payload, agent_kind)
    if tokens is None:
        return 0
    record = load_record(path)
    # Only a renewed session that never dropped below the threshold is exempt.
    exempt = bool(record and record.get("consumed_by") == session and not record.get("settled"))
    if tokens <= RENEWAL_THRESHOLD_TOKENS:
        if exempt:
            dump_json(path, {**record, "settled": True})
        return 0

    if exempt:
        if record.get("reported_over_threshold"):
            return 0
        dump_json(path, {**record, "reported_over_threshold": True})
        reason = (
            f"Context renewal: this renewed session already holds {tokens} context tokens, "
            f"above {RENEWAL_THRESHOLD_TOKENS}. Tell the user once in one line; do not renew again."
        )
    elif already_blocked_this_turn(payload, agent_kind, session):
        return 0
    else:
        reason = renewal_reason(agent_kind, session, tokens)
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
