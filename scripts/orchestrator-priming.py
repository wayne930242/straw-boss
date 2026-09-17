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

A worker's contract already reaches it at launch through the provider's
own system prompt, which survives every source that keeps that process
alive. Only a source that starts a fresh process without the launcher's
flags -- a resume -- needs this hook to hand the contract back.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from straw_boss.dispatch.state import load_json, straw_boss_root
from straw_boss.herdr.session import validate_current_process_in_pane
from straw_boss.renewal import (
    adopt_renewed_session,
    claimable_record,
    consume_record,
    current_record_path,
    payload_agent_kind,
)


# Sources that keep the launched process, and with it the contract the
# launcher put in its system prompt. An unknown source repeats the
# contract: a worker reading it twice costs context, and a worker without
# it cannot report at all.
LIVE_SYSTEM_PROMPT_SOURCES = frozenset({"startup", "clear", "compact"})


def dispatched_instruction(session_id: str) -> dict[str, object] | None:
    dispatch_dir = straw_boss_root() / "dispatch"
    for pattern in ("*.json", "archive/*.json"):
        for path in dispatch_dir.glob(pattern):
            try:
                payload = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get("session_id") == session_id:
                return payload
    return None


def orchestrator_stance() -> str:
    skill_path = Path(__file__).resolve().parent.parent / "skills" / "i-am-orchestrator" / "SKILL.md"
    text = skill_path.read_text()
    if text.startswith("---"):
        _, _, text = text.partition("---\n")
        _, _, text = text.partition("---\n")
    return text.strip()


def renewal_priming(payload: dict[str, object], session_id: str) -> str | None:
    """Continue a session renewed in this pane, primed for its recorded role."""
    agent_kind = payload_agent_kind(payload)
    path = current_record_path(payload, agent_kind)
    record = claimable_record(path, agent_kind, session_id, payload.get("source"))
    if record is None:
        return None
    record = consume_record(path, record, session_id)
    adoption = ""
    if record.get("pane_id"):
        try:
            validate_current_process_in_pane(str(record["pane_id"]))
            adopted = adopt_renewed_session(record, session_id)
        except (ValueError, OSError) as exc:
            adoption = f"\nDispatch routes were not adopted: {exc}\n"
        else:
            if adopted:
                adoption = "\nAdopted dispatch routes: " + ", ".join(adopted) + "\n"
    role = record["role"]
    sections = [
        f"# Context renewal\n\nThis session continues a {role} renewed from {path}. "
        "Continue the recorded next action now; do not ask the user to restate context."
        + adoption,
    ]
    if role == "main-agent":
        sections.append(orchestrator_stance())
    elif role == "dispatched-worker":
        for instruction_path in record.get("instruction_paths", []):
            try:
                contract = Path(str(load_json(Path(instruction_path)).get("contract_path", "")))
            except (OSError, json.JSONDecodeError):
                continue
            if contract.is_file():
                sections.append(contract.read_text().strip())
    sections.append("## Continuity record\n\n" + str(record["payload"]))
    return "\n\n".join(sections)


def priming_text(payload: dict[str, object]) -> str | None:
    session_id = payload.get("session_id") or payload.get("conversationId")
    if session_id:
        renewed = renewal_priming(payload, str(session_id))
        if renewed is not None:
            return renewed
        instruction = dispatched_instruction(str(session_id))
        if instruction is not None:
            if payload.get("source") in LIVE_SYSTEM_PROMPT_SOURCES:
                return None
            contract_path = Path(str(instruction.get("contract_path", "")))
            return contract_path.read_text().strip() if contract_path.is_file() else None
    return orchestrator_stance()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # never block session start over a malformed hook payload

    text = priming_text(payload)
    if text is None:
        return 0
    if payload_agent_kind(payload) == "agy":
        # Antigravity decodes hook stdout as its SessionStart result, not as text.
        print(json.dumps({"injectSteps": [{"ephemeralMessage": text}]}))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
