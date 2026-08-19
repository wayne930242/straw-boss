#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Archives a finished dispatch instruction and syncs plan.json.

See skills/dispatching-work/references/dispatch-mechanics.md (instruction
lifecycle) and references/plan-mechanics.md (plan status). This script
only moves/edits JSON bookkeeping files -- it never closes a herdr
pane/tab and never removes a worktree, both of which stay live tool
calls the main agent makes itself (they need live state checks this
script has no way to perform).

For a plan task, wrap-up only proceeds once the task's own status file
reports a terminal state (done/failed/cancelled) -- never on
awaiting-authorization or awaiting-user-input, which need the session to
stay alive.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def mp_dev_root() -> Path:
    return Path.home() / ".straw-boss"


def instruction_path(app: str, slug: str) -> Path:
    return mp_dev_root() / "dispatch" / f"{app}--{slug}.json"


def archived_path(app: str, slug: str) -> Path:
    return mp_dev_root() / "dispatch" / "archive" / f"{app}--{slug}.json"


def plan_path(plan_slug: str) -> Path:
    return mp_dev_root() / "plans" / plan_slug / "plan.json"


def task_status_path(plan_slug: str, task_id: str) -> Path:
    return mp_dev_root() / "plans" / plan_slug / "status" / f"{task_id}.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


def wrap_up(app: str, slug: str, plan_slug: str | None, task_id: str | None) -> dict[str, Any]:
    if (plan_slug is None) != (task_id is None):
        raise ValueError("--plan and --task-id must be given together, or not at all")

    src = instruction_path(app, slug)
    if not src.is_file():
        raise ValueError(f"no instruction file at {src}")

    plan_status: str | None = None
    if plan_slug is not None:
        assert task_id is not None
        status_path = task_status_path(plan_slug, task_id)
        if not status_path.is_file():
            raise ValueError(
                f"no status file at {status_path} yet -- wrap up only applies once "
                f"the task has reported a terminal status (done/failed/cancelled)"
            )
        plan_status = str(load_json(status_path)["status"])
        if plan_status not in ("done", "failed", "cancelled"):
            raise ValueError(
                f"task {task_id!r} status is {plan_status!r}, not terminal -- refusing "
                f"to wrap up a task that's still awaiting authorization or user input"
            )

    payload = load_json(src)
    payload["status"] = "wrapped-up"
    dest = archived_path(app, slug)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dump_json(dest, payload)
    src.unlink()

    if plan_slug is not None:
        assert task_id is not None
        plan = load_json(plan_path(plan_slug))
        task = next((t for t in plan["tasks"] if t["task_id"] == task_id), None)
        if task is None:
            raise ValueError(f"no task {task_id!r} in plan {plan_slug!r}")
        task["status"] = plan_status
        dump_json(plan_path(plan_slug), plan)

    return {"archived_path": str(dest), "plan_status": plan_status}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--plan", default=None, help="plan slug, if this was a plan task")
    parser.add_argument("--task-id", default=None, help="this task's task_id within the plan")
    args = parser.parse_args()

    try:
        result = wrap_up(args.app, args.slug, args.plan, args.task_id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
