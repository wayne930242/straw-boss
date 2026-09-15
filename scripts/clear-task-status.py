#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Discard a plan task's status file so the scheduler sees it running again.

Plan scheduling reads the status file: a task counts as in-flight while
`plan.json` says `dispatched` and its status file is not terminal
(done/failed/cancelled). A terminal status written by anything other than the
task's own worker therefore retires a task that never finished, and
`report-task-status.py` has no value that means "still running" -- every one
of its statuses is either terminal or a checkpoint the worker owns.

This is the main agent's repair for that case, and only that case: it removes
the status file, restoring the "dispatched, not yet reported" state the task
was in before the bogus write. It refuses when the plan task is not
`dispatched` (nothing to restore), and when the status file is missing or
non-terminal (nothing wrongly retired). The discarded payload is written
beside the plan and its path returned, so a later citation still resolves.

It never edits `plan.json` and never writes a status of its own -- the task's
own worker still reports its real terminal status through
`report-task-status.py` when it finishes.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from straw_boss.dispatch.state import load_json, plan_status_path, straw_boss_root

TERMINAL_STATUSES = ("done", "failed", "cancelled")


def clear_task_status(plan_slug: str, task_id: str, note: str) -> dict:
    if not note.strip():
        raise ValueError("--note must say why the status is being discarded")

    plan_path = straw_boss_root() / "plans" / plan_slug / "plan.json"
    if not plan_path.is_file():
        raise ValueError(f"no plan at {plan_path}")
    plan = load_json(plan_path)
    task = next(
        (t for t in plan.get("tasks", []) if isinstance(t, dict) and t.get("task_id") == task_id),
        None,
    )
    if task is None:
        raise ValueError(f"plan {plan_slug!r} has no task {task_id!r}")
    if task.get("status") != "dispatched":
        raise ValueError(
            f"task {task_id!r} is {task.get('status')!r} in plan.json, not 'dispatched' -- "
            f"there is no running dispatch to restore; wrap it up or re-dispatch instead"
        )

    status_path = plan_status_path(plan_slug, task_id)
    if not status_path.is_file():
        raise ValueError(
            f"no status file at {status_path} -- the task already reads as running"
        )
    payload = load_json(status_path)
    status = payload.get("status")
    if status not in TERMINAL_STATUSES:
        raise ValueError(
            f"status file reports {status!r}, which is a checkpoint the worker owns, "
            f"not a terminal status that retired the task -- resolve it through the "
            f"worker instead of discarding it"
        )

    # Printing the discarded payload is not keeping it: stdout belongs to one
    # session, and the first thing a coordinator does with a cleared task is
    # cite it to someone else. Write it beside the plan first, so the citation
    # resolves to a file that still exists.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = status_path.with_name(f"{task_id}.cleared-{stamp}.json")
    archive_path.write_text(
        json.dumps(
            {"cleared_at": stamp, "reason": note.strip(), "discarded": payload},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    status_path.unlink()
    return {
        "cleared": True,
        "status_path": str(status_path),
        "discarded_copy": str(archive_path),
        "discarded": payload,
        "note": note.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="plan slug")
    parser.add_argument("--task", required=True, help="the task_id whose status was wrongly retired")
    parser.add_argument("--note", required=True, help="why this status is being discarded")
    args = parser.parse_args()
    try:
        result = clear_task_status(args.plan, args.task, args.note)
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
