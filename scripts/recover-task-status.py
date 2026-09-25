#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Recover a dispatched task's own terminal status when its worker cannot
self-report: its pane already closed, or it is live but its report is refused.

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

`--worker-cannot-report` covers the other dead end: a live worker whose own
report keeps being refused (for example its sender identity cannot be
verified), while `close-worker-pane.py` refuses to close a pane with no
terminal status. The coordinator records the status first, then closes the
pane the normal way. It still refuses a worker herdr shows `working`, since
that worker may yet report for itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

from straw_boss.dispatch.messages import validate_note
from straw_boss.dispatch.state import (
    dump_json,
    load_herdr_pane_instruction,
    load_json,
    resolve_instruction_status_path,
)
from straw_boss.herdr.transport import (
    HerdrCommandError,
    resolve_coordinator_endpoint,
    resolve_endpoint,
    run_herdr,
    validate_current_sender,
    worker_endpoint_confirmed_closed,
)


RECOVERABLE_STATUSES = ("done", "failed")


def recover_task_status(
    instruction_path: str,
    status: str,
    note: str,
    references: list[str] | tuple[str, ...] = (),
    *,
    worker_cannot_report: bool = False,
) -> dict[str, Any]:
    if status not in RECOVERABLE_STATUSES:
        raise ValueError(
            f"--status must be one of {RECOVERABLE_STATUSES}, got {status!r} -- "
            "cancelled already has its own main-agent path through report-task-status.py"
        )
    note, normalized_references = validate_note(note, references)

    inst_path, instruction = load_herdr_pane_instruction(
        instruction_path,
        label="instruction",
        requires="closed-pane recovery only applies to a herdr-pane worker using a "
        "supported agent kind",
        undispatched_hint="it was never dispatched, so there is nothing to recover",
    )

    validate_current_sender(resolve_coordinator_endpoint(instruction))

    worker_endpoint = resolve_endpoint(instruction, "worker")
    try:
        worker_live = not worker_endpoint_confirmed_closed(worker_endpoint)
    except ValueError:
        # A pane whose conversation herdr cannot name is not proven closed.
        if not worker_cannot_report:
            raise
        worker_live = True
    if worker_live and not worker_cannot_report:
        raise ValueError(
            f"worker pane {worker_endpoint.pane_id!r} is still live -- reply to the agent "
            "and let it report its own terminal status instead of recovering on its behalf; "
            "if its own report is refused, rerun with --worker-cannot-report"
        )
    if worker_live:
        worker_status = live_worker_status(worker_endpoint.pane_id)
        if worker_status == "working":
            raise ValueError(
                f"worker pane {worker_endpoint.pane_id!r} is still working -- wait until it "
                "stops, since it may yet report its own terminal status"
            )
    elif not instruction.get("herdr_pane_closed_at"):
        # Wrap-up and roll-call read this the same way close-worker-pane.py's own
        # write does, to stop naming a close step for a pane already proven gone.
        instruction["herdr_pane_closed_at"] = datetime.now(timezone.utc).isoformat()
        dump_json(inst_path, instruction)

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
    if worker_live:
        payload["worker_live_at_recovery"] = True
    if normalized_references:
        payload["refs"] = list(normalized_references)
    dump_json(status_path, payload)
    return {"status_path": str(status_path), "status": status}


def live_worker_status(pane_id: str) -> str | None:
    try:
        agent = run_herdr(["agent", "get", pane_id]).get("result", {}).get("agent")
    except HerdrCommandError as exc:
        if exc.error_code in {"agent_not_found", "pane_not_found"}:
            return None
        raise
    status = agent.get("agent_status") if isinstance(agent, dict) else None
    return status if isinstance(status, str) else None


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
    parser.add_argument(
        "--worker-cannot-report",
        action="store_true",
        help="the worker pane is live but its own terminal report is refused",
    )
    args = parser.parse_args()

    try:
        result = recover_task_status(
            args.instruction_path, args.status, args.note, args.ref,
            worker_cannot_report=args.worker_cannot_report,
        )
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
