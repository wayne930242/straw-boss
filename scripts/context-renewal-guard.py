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
import shlex
import sys
import time
from pathlib import Path

from straw_boss import jev_renewal

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


def renewal_reason(agent_kind: str, session: str, tokens: int, threshold: int = RENEWAL_THRESHOLD_TOKENS) -> str:
    script = Path(__file__).resolve().parent / "renew-context.py"
    return (
        f"Context renewal: this turn ended with {tokens} context tokens, above "
        f"{threshold}. Renew now without asking the user. Pipe the continuity "
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
    record = load_record(path)
    if record and record.get("consumed_by") == session and not record.get("confirmed"):
        # This session reached its own Stop, so it is not a throwaway that a
        # later SessionStart in the pane may reclaim the record from.
        record = {**record, "confirmed": True}
        dump_json(path, record)
    jev_active = jev_renewal.enabled(agent_kind, session)
    threshold = jev_renewal.threshold() if jev_active and agent_kind == "claude" else RENEWAL_THRESHOLD_TOKENS
    tokens = jev_renewal.current_tokens(payload) if jev_active and agent_kind == "claude" else context_tokens(payload, agent_kind)
    if tokens is None:
        return 0
    if (jev_active and agent_kind == "codex" and record
            and record.get("consumed_by") == session and record.get("jev_request")):
        from straw_boss.jev_codex_renewal import observe
        try:
            observe(record, session, tokens)
        except (OSError, ValueError, KeyError):
            print("Jev usage observation could not be persisted.", file=sys.stderr)
    if (agent_kind == "codex" and record and record.get("consumed_by") == session
            and not record.get("usage_recorded")):
        from straw_boss import renewal_usage
        try:
            renewal_usage.record_renewal(record, session, Path(payload["transcript_path"]))
            record = {**record, "usage_recorded": True}
            dump_json(path, record)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            print("Codex renewal usage could not be recorded.", file=sys.stderr)
    # Only a renewed session that never dropped below the threshold is exempt.
    exempt = bool(record and record.get("consumed_by") == session and not record.get("settled"))
    if tokens <= threshold:
        if (agent_kind == "codex"
                and not (record and record.get("jev_candidate_session") == session)):
            from straw_boss import renewal_usage
            try:
                renewal_usage.record_native_compaction(
                    session, os.environ.get("HERDR_PANE_ID"), Path(payload["transcript_path"]))
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                print("Native compaction usage could not be recorded.", file=sys.stderr)
        if exempt:
            dump_json(path, {**record, "settled": True})
        return 0

    if exempt:
        if record.get("reported_over_threshold"):
            return 0
        dump_json(path, {**record, "reported_over_threshold": True})
        reason = (
            f"Context renewal: this renewed session already holds {tokens} context tokens, "
            f"above {threshold}. Tell the user once in one line; do not renew again."
        )
    elif already_blocked_this_turn(payload, agent_kind, session):
        return 0
    else:
        reason = renewal_reason(agent_kind, session, tokens, threshold)
        if jev_active and agent_kind == "codex":
            transcript = shlex.quote(str(payload["transcript_path"]))
            reason += f" Add --transcript-path {transcript}; Jev is attempted before ordinary continuity renewal."
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
