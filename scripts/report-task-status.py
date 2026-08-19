#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Write a dispatched task's own completion/failure status.

Given to every task dispatched as part of a plan (see
skills/dispatching-work/references/plan-mechanics.md). Writes only this
task's own status file -- never plan.json, never another task's file --
so concurrent reports from different tasks never contend for the same
path.

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


def plans_root() -> Path:
    return Path.home() / ".straw-boss" / "plans"


def status_path(plan_slug: str, task_id: str) -> Path:
    return plans_root() / plan_slug / "status" / f"{task_id}.json"


VALID_STATUSES = ("done", "failed", "awaiting-authorization", "awaiting-user-input", "cancelled")


def report_status(plan_slug: str, task_id: str, status: str, note: str) -> Path:
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")

    path = status_path(plan_slug, task_id)
    if not path.parent.is_dir():
        raise ValueError(
            f"status directory {path.parent} does not exist -- "
            f"unknown plan {plan_slug!r} or task {task_id!r} not part of it"
        )

    payload = {
        "status": status,
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="plan slug")
    parser.add_argument("--task", required=True, help="this task's task_id")
    parser.add_argument("--status", required=True, choices=VALID_STATUSES)
    parser.add_argument("--note", default="", help="optional free-text note")
    args = parser.parse_args()

    try:
        path = report_status(args.plan, args.task, args.status, args.note)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
