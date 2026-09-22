#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Adopt one live dispatch after its worker agent restarted in the same pane.

`adopt-dispatch.py` covers the coordinator side and says so: it never touches
the worker endpoint. Nothing covered the mirror image. A worker that restarts in
its own pane keeps the pane and the tab, and takes a new terminal and a new
provider conversation. Every main-side send then refuses on a terminal or
session mismatch, and for a Codex or Antigravity worker dispatched before its
conversation id was recorded, the terminal *is* the whole identity, so the
refusal is total: the coordinator holds verified findings with no channel to
hand them over. `rebind-dispatch.py` does not help -- it needs a Codex main
agent, and it re-points at launch-era sessions rather than at whatever now runs.

Ownership follows the pane, as it does for adoption on the main side. The
coordinator proves itself live in its own pane, and the pane, tab, agent kind
and working directory recorded at dispatch must all still match what herdr
reports. A conversation id already on record is treated as identity, not
routing: if it differs from the live one this is a different agent rather than a
restart, and the dispatch is refused instead of quietly re-pointed at a stranger.

Adopting also records the live conversation id when the dispatch never had one,
so identity stops depending on a terminal that any restart replaces.

This command changes recorded worker routing metadata only. It never reports
task status, never sends a message, and never touches the main endpoint. The
adoption is recorded with its before and after values so the change stays
auditable.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from straw_boss.dispatch.state import dump_json, load_json
from straw_boss.herdr.session import (
    resolve_coordinator_endpoint,
    resolve_endpoint,
    run_herdr,
    session_value,
    validate_current_sender,
    validate_live_session,
)


def live_worker_agent(pane_id: str) -> dict[str, Any]:
    payload = run_herdr(["agent", "get", pane_id])
    agent = payload.get("result", {}).get("agent")
    if not isinstance(agent, dict) or agent.get("pane_id") != pane_id:
        raise ValueError(f"herdr reports no agent in worker pane {pane_id!r}")
    return agent


def adopted_changes(
    instruction: dict[str, Any], agent: dict[str, Any], worker_session_id: str
) -> dict[str, Any]:
    """What the recorded worker endpoint becomes, once the pane still proves it."""
    previous = resolve_endpoint(instruction, "worker")
    if agent.get("agent") != previous.agent_kind:
        raise ValueError(
            f"worker pane {previous.pane_id!r} now runs agent kind "
            f"{agent.get('agent')!r}, not the dispatched {previous.agent_kind!r}; "
            "this is a different worker, so dispatch the work again"
        )
    for field, recorded in (("tab_id", "herdr_tab_id"), ("cwd", "repo_root")):
        expected = instruction.get(recorded)
        # A field this herdr does not report is not evidence of a mismatch.
        if expected and agent.get(field) and agent[field] != expected:
            raise ValueError(
                f"worker pane {previous.pane_id!r} reports {field} "
                f"{agent.get(field)!r}, not the dispatched {expected!r}; "
                "adoption covers a restart in place, not a relocated worker"
            )
    live_session = session_value(agent)
    if not live_session:
        raise ValueError(
            f"herdr reports no conversation id for the agent in pane "
            f"{previous.pane_id!r}; adoption needs a corroborated identity"
        )
    if live_session != worker_session_id:
        raise ValueError(
            f"--worker-session-id {worker_session_id!r} is not the conversation "
            f"herdr places in pane {previous.pane_id!r}; refusing to record an "
            "identity this pane cannot corroborate"
        )
    if previous.expected_session_id:
        if previous.expected_session_id == live_session:
            raise ValueError(
                "the recorded worker conversation is still the one in this pane -- "
                "nothing to adopt; the refusal you saw has another cause"
            )
        raise ValueError(
            f"pane {previous.pane_id!r} holds conversation {live_session!r}, not the "
            f"recorded {previous.expected_session_id!r}; a restart keeps its "
            "conversation, so this is a different agent -- dispatch the work again"
        )
    terminal = agent.get("terminal_id")
    if not isinstance(terminal, str) or not terminal:
        raise ValueError(f"worker pane {previous.pane_id!r} has no live terminal id")
    return {"session_id": live_session, "herdr_terminal_id": terminal}


def adopt_worker_endpoint(
    instruction_path: str, worker_session_id: str, references: list[str]
) -> dict[str, Any]:
    worker_session_id = worker_session_id.strip()
    if not worker_session_id:
        raise ValueError("--worker-session-id must name the conversation now in the worker pane")
    path = Path(instruction_path).resolve()
    if not path.is_file():
        raise ValueError(f"no instruction file at {path}")
    instruction = load_json(path)
    if instruction.get("mode") != "herdr-pane":
        raise ValueError("adoption applies to an interactive herdr-pane dispatch")
    if instruction.get("status") != "in-progress":
        raise ValueError(
            "adoption requires an in-progress dispatch; a pending one is rewritten by "
            "dispatch-task.py and a wrapped one needs no worker endpoint"
        )
    # Only the live coordinator may re-point its own dispatch.
    validate_current_sender(resolve_coordinator_endpoint(instruction))

    previous = resolve_endpoint(instruction, "worker")
    changes = adopted_changes(instruction, live_worker_agent(previous.pane_id), worker_session_id)

    candidate_instruction = {**instruction, **changes}
    # Prove the repair before writing it: the adopted endpoint is the one every
    # main-side command validates against from here on, so if it cannot pass
    # now, recording it would only move the refusal.
    adopted = resolve_endpoint(candidate_instruction, "worker")
    validate_live_session(adopted)
    if load_json(path) != instruction:
        raise ValueError("instruction changed during adoption; retry from fresh state")

    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "refs": references,
        "before": {key: instruction.get(key) for key in changes},
        "after": changes,
    }
    candidate_instruction["worker_endpoint_adoptions"] = [
        *instruction.get("worker_endpoint_adoptions", []),
        record,
    ]
    dump_json(path, candidate_instruction)
    return {
        "adopted": True,
        "instruction_path": str(path),
        "pane_id": adopted.pane_id,
        "previous_herdr_terminal_id": previous.expected_terminal_id,
        "herdr_terminal_id": adopted.expected_terminal_id,
        "worker_session_id": adopted.expected_session_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--instruction-path",
        required=True,
        help="dispatch whose worker restarted in its recorded pane",
    )
    parser.add_argument(
        "--worker-session-id",
        required=True,
        help="the conversation id herdr now reports for the worker pane; recording it "
        "ends this dispatch's dependence on a terminal id that any restart replaces",
    )
    parser.add_argument("--ref", action="append", default=[], help="artifact/evidence reference")
    args = parser.parse_args()
    try:
        result = adopt_worker_endpoint(args.instruction_path, args.worker_session_id, args.ref)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
