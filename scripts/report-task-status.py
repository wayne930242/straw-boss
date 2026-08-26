#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Write a dispatched task's own completion/failure status.

Given to every dispatched task, plan or standalone (see
skills/dispatching-work/references/plan-mechanics.md and
dispatch-mechanics.md). Writes only this task's own status file -- never
plan.json, never another task's file -- so concurrent reports from
different tasks never contend for the same path.

This is the provider-neutral durable state interface. For a plan task,
watch-plan-status.py turns each file-content revision into the scheduling
event that drives wave computation. For a live instruction, this command
validates the reporting sender before writing, then validates and notifies the
main-agent endpoint through the shared transport.

Two ways to address which task's status file to write, mutually
exclusive:

  --plan/--task            plan task, by plan slug + task_id -- unchanged
                            from before this script also supported
                            standalone dispatches. Writes to the existing
                            <home>/.straw-boss/plans/<slug>/status/<task_id>.json.
  --instruction-path        either kind of dispatch, by its own
                            instruction file
                            (<home>/.straw-boss/dispatch/<app>--<slug>.json).
                            If that file carries plan_id/task_id, this
                            resolves to the exact same plan status-file
                            location as --plan/--task above. Otherwise
                            (a standalone dispatch) it writes to a
                            sibling <app>--<slug>.status.json next to the
                            instruction file. A dispatched agent should
                            prefer this form -- it already knows its own
                            instruction path and does not need to know
                            whether it's a plan or standalone task.

--status cancelled is the one exception to "given to the task": the main
agent calls this itself, for a task it is ending because the dispatch
was wrong, not because the task reported on itself (see
skills/dispatching-work/references/cross-session-coordination.md's
Cancel section) -- a dispatched task never reports its own cancellation,
since it never sees this happen.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dispatch_state import (
    load_json,
    plan_status_path,
    resolve_instruction_status_path,
)
from dispatch_transport import (
    normalize_references,
    send_instruction_message,
    validate_delta_message,
    validate_status_sender,
)


def status_path(plan_slug: str, task_id: str) -> Path:
    return plan_status_path(plan_slug, task_id)


VALID_STATUSES = (
    "done",
    "failed",
    "awaiting-authorization",
    "awaiting-user-input",
    "awaiting-main-agent",
    "cancelled",
)


def resolve_status_path(plan_slug: str | None, task_id: str | None, instruction_path: str | None) -> Path:
    using_plan_task = plan_slug is not None and task_id is not None
    using_instruction = instruction_path is not None
    if using_plan_task == using_instruction:
        raise ValueError("give either --plan/--task together, or --instruction-path, not both and not neither")

    if using_plan_task:
        assert plan_slug is not None and task_id is not None
        path = status_path(plan_slug, task_id)
        if not path.parent.is_dir():
            raise ValueError(
                f"status directory {path.parent} does not exist -- "
                f"unknown plan {plan_slug!r} or task {task_id!r} not part of it"
            )
        return path

    assert instruction_path is not None
    inst_path = Path(instruction_path)
    if not inst_path.is_file():
        raise ValueError(f"no instruction file at {inst_path}")
    payload = load_json(inst_path)
    return resolve_instruction_status_path(inst_path, payload)


def report_status(
    plan_slug: str | None,
    task_id: str | None,
    instruction_path: str | None,
    status: str,
    note: str,
    references: list[str] | tuple[str, ...] = (),
) -> Path:
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    try:
        note = validate_delta_message(note)
    except ValueError as exc:
        raise ValueError(str(exc).replace("message", "--note", 1)) from exc
    normalized_references = normalize_references(references)

    if instruction_path is not None:
        validate_status_sender(instruction_path, status)

    path = resolve_status_path(plan_slug, task_id, instruction_path)

    payload = {
        "status": status,
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if normalized_references:
        payload["refs"] = list(normalized_references)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def notify_main_agent(
    instruction_path: str,
    status: str,
    note: str,
    references: list[str] | tuple[str, ...] = (),
) -> bool:
    inst_path = Path(instruction_path)
    payload = load_json(inst_path)
    pane_id = payload.get("main_agent_herdr_pane_id")
    if not pane_id:
        return False

    send_instruction_message(
        inst_path,
        "main",
        "status",
        f"{status} — {note}",
        references=references,
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default=None, help="plan slug (give together with --task, or use --instruction-path instead)")
    parser.add_argument("--task", default=None, help="this task's task_id (give together with --plan)")
    parser.add_argument(
        "--instruction-path",
        default=None,
        help="path to this dispatch's own instruction file (alternative to --plan/--task, works for either kind)",
    )
    parser.add_argument("--status", required=True, choices=VALID_STATUSES)
    parser.add_argument("--note", required=True, help="outcome or exact unblock, at most two sentences")
    parser.add_argument("--ref", action="append", default=[], help="artifact/evidence reference")
    args = parser.parse_args()

    try:
        path = report_status(
            args.plan,
            args.task,
            args.instruction_path,
            args.status,
            args.note,
            args.ref,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {path}")
    if args.instruction_path is not None and args.status != "cancelled":
        try:
            notified = notify_main_agent(
                args.instruction_path, args.status, args.note, args.ref
            )
        except ValueError as exc:
            print(f"error: status remains written at {path}, but {exc}", file=sys.stderr)
            return 1
        if notified:
            print("notified main agent through herdr")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
