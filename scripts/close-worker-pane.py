#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Close a wrapped-up dispatch's worker pane and rebalance the columns it leaves.

See skills/dispatching-work/SKILL.md's "Wrap up". Closing a column hands its
width to whichever neighbour absorbs it, so a tab that `launch-dispatched-agent.py`
balanced on every split drifts wider and wider on every close. Closing through
this script keeps the two halves of that move together.

It is separate from `wrap-up-task.py` because that script commits itself to pure
JSON bookkeeping with no herdr dependency (see its own docstring), and closing a
pane is a live herdr call.
"""

from __future__ import annotations

import argparse
import json
import sys

from straw_boss.dispatch.launch.pane import close_worker_pane
from straw_boss.dispatch.state import (
    load_herdr_pane_instruction,
    load_json,
    resolve_instruction_status_path,
)
from straw_boss.herdr.transport import resolve_endpoint, validate_current_sender


TERMINAL_STATUSES = ("done", "failed", "cancelled")


def close_dispatch_pane(instruction_path: str) -> dict[str, str | None]:
    inst_path, instruction = load_herdr_pane_instruction(
        instruction_path,
        label="dispatch instruction",
        requires="only a herdr-pane dispatch has a worker pane to close",
        undispatched_hint="nothing was launched for it, so there is no pane to close",
    )

    validate_current_sender(resolve_endpoint(instruction, "main"))

    status_path = resolve_instruction_status_path(inst_path, instruction)
    if not status_path.is_file():
        raise ValueError(
            f"no status file at {status_path} -- a live worker writes its own terminal "
            f"status, so refusing to close a pane out from under one. If the pane is "
            f"already gone, use recover-task-status.py --instruction-path {inst_path}"
        )
    status = str(load_json(status_path)["status"])
    if status not in TERMINAL_STATUSES:
        raise ValueError(
            f"dispatch status is {status!r}, not terminal -- refusing to close the pane "
            f"of a worker still awaiting authorization, user input, or main-agent action"
        )

    pane_id = str(instruction["herdr_pane_id"])
    balance_warning = close_worker_pane(
        pane_id, instruction.get("main_agent_herdr_pane_id")
    )
    return {
        "closed_pane_id": pane_id,
        "status": status,
        "balance_warning": balance_warning,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--instruction-path",
        required=True,
        help="path to the terminal dispatch's own instruction file",
    )
    args = parser.parse_args()

    try:
        result = close_dispatch_pane(args.instruction_path)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
