#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Adopt one live dispatch after its Claude main agent restarted or moved panes.

Two things happen to a coordinator that leave every dispatch it made recorded
against an identity no main-side command can satisfy:

- It restarts in its own pane. The pane stays, the provider conversation is
  new, and the recorded main session id is genuinely stale.
  `validate_current_sender` then refuses every main-side command for those
  dispatches -- `recover-task-status.py`, `reply-to-worker.py`,
  `send-dispatch-message.py` -- and it is right to: the caller is provably not
  the conversation that dispatched the work. Ownership follows the pane: the
  successor genuinely running inside the recorded main pane owns what that
  pane dispatched.
- Its conversation resumes in a different pane. The session id is the same,
  the recorded pane is gone or somebody else's, and every main-side command
  refuses on a sender pane mismatch while worker status reports land in the
  delivery ledger as undeliverable. Ownership follows the session: the
  conversation that dispatched the work, verified live in its new pane, owns
  it.

Nothing else covers either case. `rebind-dispatch.py` is Codex-only and refuses
a supplied session that differs from the recorded one; `pin_codex_main_agent`
only ever pins Codex, and at launch.

Both proofs use the same process-tree check `rebind-dispatch.py` uses for its
own pane-scoped action, so a stray process that merely knows the instruction
path cannot satisfy either: the caller's own process tree must run inside the
pane it adopts from, and the Claude session registry keyed on that pane's
foreground process must place the supplied session there. A restart adopts only
from the recorded main pane; a move adopts only the recorded main session, and
only while the recorded pane no longer hosts it.

This command changes recorded main routing metadata only. It never reports task
status, never sends a message, and never touches the worker endpoint. The
adoption is recorded with its before and after values so the change stays
auditable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from straw_boss.dispatch.state import dump_json, load_json
from straw_boss.herdr.session import (
    Endpoint,
    HerdrCommandError,
    HerdrUnavailableError,
    claude_registry_session,
    resolve_endpoint,
    validate_current_process_in_pane,
    validate_live_session,
)


ENDPOINT_MISSING_ERROR_CODES = frozenset({"agent_not_found", "pane_not_found"})


def corroborated_session(pane_id: str, main_session_id: str) -> str:
    """The session the caller claims to be, as the pane it runs in proves it."""
    validate_current_process_in_pane(pane_id)
    current_session = claude_registry_session(pane_id)
    if not current_session:
        raise ValueError(
            f"could not resolve the Claude session now running in pane {pane_id!r}; "
            "adoption needs a corroborated identity"
        )
    if current_session != main_session_id:
        raise ValueError(
            f"--main-session-id {main_session_id!r} is not the session the Claude "
            f"registry places in pane {pane_id!r}; refusing to record an "
            "identity this pane cannot corroborate"
        )
    return current_session


def adopt_in_recorded_pane(previous: Endpoint, main_session_id: str) -> dict[str, Any]:
    """A new conversation in the recorded main pane takes the session over."""
    current_session = corroborated_session(previous.pane_id, main_session_id)
    if current_session == previous.expected_session_id:
        raise ValueError(
            "the recorded main session is still the one in this pane -- nothing to adopt; "
            "the refusal you saw has another cause"
        )
    return {"main_agent_session_id": current_session}


def recorded_pane_still_hosts(previous: Endpoint) -> bool:
    """Whether herdr still places the recorded session in the recorded pane.

    Only herdr's answer decides: a pane or agent it reports missing, or an
    identity it reports as someone else's, means the session left. No answer
    at all -- a timeout, a missing CLI, garbled output -- propagates, so a
    transient failure against the old pane cannot let a move through early.
    """
    try:
        validate_live_session(previous)
    except HerdrUnavailableError:
        raise
    except HerdrCommandError as exc:
        if exc.error_code in ENDPOINT_MISSING_ERROR_CODES:
            return False
        raise
    except ValueError:
        return False
    return True


def adopt_from_new_pane(
    previous: Endpoint, current_pane: str, main_session_id: str
) -> dict[str, Any]:
    """The recorded conversation, now in another pane, takes the route with it."""
    current_session = corroborated_session(current_pane, main_session_id)
    if current_session != previous.expected_session_id:
        raise ValueError(
            f"pane {current_pane!r} holds session {current_session!r}, not the recorded "
            f"main session {previous.expected_session_id!r}; a different conversation "
            f"adopts only from the recorded main pane {previous.pane_id!r}"
        )
    if recorded_pane_still_hosts(previous):
        raise ValueError(
            f"the recorded main pane {previous.pane_id!r} still hosts session "
            f"{current_session!r} -- nothing to move; the refusal you saw has another cause"
        )
    return {"main_agent_herdr_pane_id": current_pane}


def adopt_dispatch(instruction_path: str, main_session_id: str) -> dict[str, Any]:
    main_session_id = main_session_id.strip()
    if not main_session_id:
        raise ValueError("--main-session-id must name the session adopting this dispatch")
    path = Path(instruction_path).resolve()
    if not path.is_file():
        raise ValueError(f"no instruction file at {path}")
    instruction = load_json(path)
    if instruction.get("mode") != "herdr-pane":
        raise ValueError("adoption applies to an interactive herdr-pane dispatch")
    if instruction.get("status") != "in-progress":
        raise ValueError(
            "adoption requires an in-progress dispatch; a pending one is rewritten by "
            "dispatch-task.py and a wrapped one needs no main endpoint"
        )
    main_agent_kind = instruction.get("main_agent_kind")
    if main_agent_kind != "claude":
        hint = (
            "a resumed Codex coordinator uses rebind-dispatch.py"
            if main_agent_kind == "codex"
            else f"no adoption command exists for main agent kind {main_agent_kind!r}"
        )
        raise ValueError(f"this recovery command covers a Claude main agent; {hint}")

    previous = resolve_endpoint(instruction, "main")
    current_pane = os.environ.get("HERDR_PANE_ID")
    if current_pane and current_pane != previous.pane_id:
        changes = adopt_from_new_pane(previous, current_pane, main_session_id)
    else:
        changes = adopt_in_recorded_pane(previous, main_session_id)

    candidate_instruction = {**instruction, **changes}
    # Prove the repair before writing it: the adopted endpoint is the one every
    # main-side command validates against from here on, so if it cannot pass
    # now, recording it would only move the refusal.
    adopted = resolve_endpoint(candidate_instruction, "main")
    validate_live_session(adopted)
    if load_json(path) != instruction:
        raise ValueError("instruction changed during adoption; retry from fresh state")

    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "before": {key: instruction.get(key) for key in changes},
        "after": changes,
    }
    candidate_instruction["main_agent_adoptions"] = [
        *instruction.get("main_agent_adoptions", []),
        record,
    ]
    dump_json(path, candidate_instruction)
    return {
        "adopted": True,
        "instruction_path": str(path),
        "previous_pane_id": previous.pane_id,
        "pane_id": adopted.pane_id,
        "previous_main_session_id": previous.expected_session_id,
        "main_session_id": adopted.expected_session_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--instruction-path",
        required=True,
        help="dispatch this coordinator made before it restarted or moved panes",
    )
    parser.add_argument(
        "--main-session-id",
        required=True,
        help="the session id this pane is adopting the dispatch as; it must match the "
        "session the Claude registry places in the caller's own pane -- a new session "
        "in the recorded main pane, or the recorded session in a new pane",
    )
    args = parser.parse_args()
    try:
        result = adopt_dispatch(args.instruction_path, args.main_session_id)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
