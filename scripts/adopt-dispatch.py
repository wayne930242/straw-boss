#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Adopt one live dispatch after the main agent restarted in its own pane.

A coordinator that restarts keeps its Herdr pane but starts a new provider
conversation, so every dispatch it made before the restart records a main
session id that is now genuinely stale. `validate_current_sender` then refuses
every main-side command for those dispatches -- `recover-task-status.py`,
`reply-to-worker.py`, `send-dispatch-message.py` -- and it is right to: the
caller is provably not the conversation that dispatched the work. Nothing else
covers the case. `rebind-dispatch.py` is Codex-only and refuses a supplied
session that differs from the recorded one, which is exactly what a restart
produces; `pin_codex_main_agent` only ever pins Codex, and at launch.

This command changes recorded main routing metadata only. It never reports task
status, never sends a message, and never touches the worker endpoint.

The pane is the workroom, so the successor genuinely running inside the
recorded main pane owns what that pane dispatched. That is proved by the same
process-tree check `rebind-dispatch.py` uses for its own pane-scoped action: a
stray process that merely knows the instruction path cannot satisfy it, which
is the property the sender guard exists to keep. The predecessor conversation
surviving in some other pane does not retain ownership here -- ownership
follows the pane, and the adoption is recorded with both session ids so the
change stays auditable.
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
    claude_registry_session,
    resolve_endpoint,
    validate_current_process_in_pane,
    validate_live_session,
)


def adopt_dispatch(instruction_path: str, main_session_id: str) -> dict[str, Any]:
    if not main_session_id.strip():
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
    if instruction.get("main_agent_kind") != "claude":
        raise ValueError(
            "this recovery command covers a Claude main agent; a resumed Codex "
            "coordinator uses rebind-dispatch.py"
        )

    previous = resolve_endpoint(instruction, "main")
    validate_current_process_in_pane(previous.pane_id)

    current_session = claude_registry_session(previous.pane_id)
    if not current_session:
        raise ValueError(
            f"could not resolve the Claude session now running in pane {previous.pane_id!r}; "
            "adoption needs a corroborated successor identity"
        )
    if current_session == previous.expected_session_id:
        raise ValueError(
            "the recorded main session is still the one in this pane -- nothing to adopt; "
            "the refusal you saw has another cause"
        )
    if current_session != main_session_id.strip():
        raise ValueError(
            f"--main-session-id {main_session_id.strip()!r} is not the session the Claude "
            f"registry places in pane {previous.pane_id!r}; refusing to record an "
            "identity this pane cannot corroborate"
        )

    changes = {"main_agent_session_id": current_session}
    candidate_instruction = {**instruction, **changes}
    # Prove the repair before writing it: the adopted endpoint is the one every
    # main-side command validates against from here on, so if it cannot pass
    # now, recording it would only move the refusal.
    validate_live_session(resolve_endpoint(candidate_instruction, "main"))
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
        "pane_id": previous.pane_id,
        "previous_main_session_id": previous.expected_session_id,
        "main_session_id": current_session,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--instruction-path",
        required=True,
        help="dispatch this restarted coordinator made in its previous session",
    )
    parser.add_argument(
        "--main-session-id",
        required=True,
        help="the session id this pane is adopting the dispatch as; it must match the "
        "session the Claude registry places in the recorded main pane",
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
