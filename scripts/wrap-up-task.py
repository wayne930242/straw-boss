#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Archives a finished dispatch instruction and syncs plan.json.

See skills/dispatching-work/references/dispatch-mechanics.md (instruction
lifecycle) and references/plan-mechanics.md (plan status). This script
only moves/edits JSON bookkeeping files -- it never closes the worker pane or
removes a worktree. Those stay live tool calls the main agent makes itself; the
shared coordinator tab is never part of dispatch cleanup.

For a plan task, wrap-up only proceeds once the task's own status file
reports a terminal state (done/failed/cancelled) -- never on
awaiting-authorization, awaiting-user-input, or awaiting-main-agent,
which need the session to stay alive.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dispatch_state import dump_json, load_json, straw_boss_root


def instruction_path(app: str, slug: str) -> Path:
    return straw_boss_root() / "dispatch" / f"{app}--{slug}.json"


def archived_path(app: str, slug: str) -> Path:
    return straw_boss_root() / "dispatch" / "archive" / f"{app}--{slug}.json"


def sibling_paths(app: str, slug: str) -> list[Path]:
    """Artifacts owned by one instruction and archived with it."""
    base = straw_boss_root() / "dispatch"
    stem = f"{app}--{slug}"
    return [
        base / f"{stem}.status.json",
        base / f"{stem}.progress.jsonl",
        base / f"{stem}.contract.md",
        base / f"{stem}.launch.json",
        base / f"{stem}.messages.jsonl",
    ]


def plan_path(plan_slug: str) -> Path:
    return straw_boss_root() / "plans" / plan_slug / "plan.json"


def task_status_path(plan_slug: str, task_id: str) -> Path:
    return straw_boss_root() / "plans" / plan_slug / "status" / f"{task_id}.json"


def wrap_up(app: str, slug: str, plan_slug: str | None, task_id: str | None) -> dict[str, Any]:
    if (plan_slug is None) != (task_id is None):
        raise ValueError("--plan and --task-id must be given together, or not at all")

    src = instruction_path(app, slug)
    if not src.is_file():
        raise ValueError(f"no instruction file at {src}")
    payload = load_json(src)

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
                f"to wrap up a task that's still awaiting authorization, user input, "
                f"or main-agent action"
            )
    else:
        # A standalone dispatch's own report-task-status.py --instruction-path record
        # (see dispatch-mechanics.md's "Reporting scripts") -- same non-terminal guard
        # as the plan-task case above. A missing record is legitimate for an older
        # dispatch or a claude-p one confirmed done by process exit, but not for a
        # confirmed herdr-pane worker: that one has a live pane and writes its own
        # status, so silence means it never reported, not that it finished.
        standalone_status_path = sibling_paths(app, slug)[0]
        if standalone_status_path.is_file():
            standalone_status = str(load_json(standalone_status_path)["status"])
            if standalone_status not in ("done", "failed", "cancelled"):
                raise ValueError(
                    f"dispatch {app}--{slug} status is {standalone_status!r}, not terminal -- refusing "
                    f"to wrap up a dispatch that's still awaiting authorization, user input, "
                    f"or main-agent action"
                )
        elif payload.get("mode") == "herdr-pane" and payload.get("status") == "in-progress":
            # This call cannot tell a running worker from a closed one, so it
            # refuses rather than archiving the instruction out from under a live
            # agent -- including one dispatched by a different main-agent session,
            # the case the sibling-status check above cannot see at all. `pending`
            # stays archivable: never confirmed, so nothing was launched to protect.
            raise ValueError(
                f"dispatch {app}--{slug} is still in-progress with no status record at "
                f"{standalone_status_path} -- a live herdr-pane worker writes its own "
                f"terminal status, so refusing to archive it out from under one. Reply to "
                f"the agent and let it report; if its pane is confirmed closed, write an "
                f"explicit terminal status with recover-task-status.py --instruction-path "
                f"{src} first"
            )

    payload["status"] = "wrapped-up"
    dest = archived_path(app, slug)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dump_json(dest, payload)
    src.unlink()

    for sibling in sibling_paths(app, slug):
        if sibling.is_file():
            sibling.rename(dest.parent / sibling.name)

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
