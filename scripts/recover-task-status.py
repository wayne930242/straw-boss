#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Recover a dispatched task's own terminal status when its worker pane
already closed before it could self-report.

See skills/dispatching-work/SKILL.md's "Branch: Wrap up an instruction" and
references/dispatch-mechanics.md's "Closing an instruction". Normal order
stays: reply to the agent, let it call `report-task-status.py` on itself,
then close the pane and wrap up -- that script's own sender validation
enforces exactly that by refusing anyone but the live worker pane. This
script is the one exception, for the case that guard cannot help with: a
worker pane that already closed before it wrote its own terminal status. It
is a separate script rather than a flag on `wrap-up-task.py` because that
script commits itself to pure JSON bookkeeping with no herdr dependency
(see its own docstring); the closed-pane check here needs a live herdr
probe, which stays out of `wrap-up-task.py` entirely.

It never infers a status value from the pane being closed -- the caller
states `done` or `failed` and a traceable note itself. `--status cancelled`
already has its own main-agent path through `report-task-status.py` (main
resolves as sender for that status, so it never depends on the worker pane
at all) and is out of scope here. Refuses unless: the caller is genuinely
the live main agent pane recorded on the dispatch; the worker pane is
confirmed unreachable, not merely believed closed; and no terminal status is
already on file for this task.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dispatch_state import dump_json, load_json, resolve_instruction_status_path
from dispatch_transport import (
    normalize_references,
    resolve_endpoint,
    validate_current_sender,
    validate_delta_message,
    worker_endpoint_confirmed_closed,
)


RECOVERABLE_STATUSES = ("done", "failed")


def recover_task_status(
    instruction_path: str,
    status: str,
    note: str,
    references: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    if status not in RECOVERABLE_STATUSES:
        raise ValueError(
            f"--status must be one of {RECOVERABLE_STATUSES}, got {status!r} -- "
            "cancelled already has its own main-agent path through report-task-status.py"
        )
    try:
        note = validate_delta_message(note)
    except ValueError as exc:
        raise ValueError(str(exc).replace("message", "--note", 1)) from exc
    normalized_references = normalize_references(references)

    inst_path = Path(instruction_path)
    if not inst_path.is_file():
        raise ValueError(f"no instruction file at {inst_path}")
    instruction = load_json(inst_path)

    mode = instruction.get("mode")
    agent_kind = instruction.get("agent_kind")
    if mode != "herdr-pane" or agent_kind not in ("claude", "codex"):
        raise ValueError(
            f"instruction {inst_path} is mode={mode!r} agent_kind={agent_kind!r} -- "
            "closed-pane recovery only applies to a herdr-pane worker using a supported agent kind"
        )
    if not instruction.get("herdr_pane_id"):
        raise ValueError(
            f"instruction {inst_path} has no herdr_pane_id recorded -- it was never "
            "dispatched, so there is nothing to recover"
        )

    validate_current_sender(resolve_endpoint(instruction, "main"))

    worker_endpoint = resolve_endpoint(instruction, "worker")
    if not worker_endpoint_confirmed_closed(worker_endpoint):
        raise ValueError(
            f"worker pane {worker_endpoint.pane_id!r} is still live -- reply to the agent "
            "and let it report its own terminal status instead of recovering on its behalf"
        )

    status_path = resolve_instruction_status_path(inst_path, instruction)
    if status_path.is_file():
        existing_status = load_json(status_path).get("status")
        if existing_status in ("done", "failed", "cancelled"):
            raise ValueError(
                f"status file {status_path} already reports terminal status "
                f"{existing_status!r} -- no recovery needed"
            )

    payload = {
        "status": status,
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "recovered_by_main_agent": True,
    }
    if normalized_references:
        payload["refs"] = list(normalized_references)
    dump_json(status_path, payload)
    return {"status_path": str(status_path), "status": status}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--instruction-path",
        required=True,
        help="path to the closed-pane worker's own dispatch instruction file",
    )
    parser.add_argument("--status", required=True, choices=RECOVERABLE_STATUSES)
    parser.add_argument(
        "--note", required=True, help="explicit terminal status reasoning, at most two sentences"
    )
    parser.add_argument("--ref", action="append", default=[], help="artifact/evidence reference")
    args = parser.parse_args()

    try:
        result = recover_task_status(args.instruction_path, args.status, args.note, args.ref)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
