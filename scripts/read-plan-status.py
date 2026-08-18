#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Targeted reads of a plan's state -- never dumps everything by default.

See skills/dispatching-work/references/plan-mechanics.md. Prefer the
narrowest query that answers the actual question: --task for one task,
--not-done or --ready for a filtered list. --full is for the rare case
of actually wanting the whole plan.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def plan_path(plan_slug: str) -> Path:
    return Path.home() / ".straw-boss" / "plans" / plan_slug / "plan.json"


def status_dir(plan_slug: str) -> Path:
    return Path.home() / ".straw-boss" / "plans" / plan_slug / "status"


def load_plan(plan_slug: str) -> dict[str, Any]:
    path = plan_path(plan_slug)
    if not path.is_file():
        raise ValueError(f"no plan found at {path}")
    return json.loads(path.read_text())


def load_task_status_file(plan_slug: str, task_id: str) -> dict[str, Any] | None:
    path = status_dir(plan_slug) / f"{task_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def effective_status(plan_slug: str, task: dict[str, Any]) -> str:
    """The status file (done/failed), if it exists, is authoritative --
    it reflects what the dispatched task itself reported. Otherwise fall
    back to plan.json's own tracked status (planned/dispatched)."""
    reported = load_task_status_file(plan_slug, task["task_id"])
    if reported is not None:
        return str(reported["status"])
    return str(task["status"])


def ready_wave(plan_slug: str, plan: dict[str, Any]) -> list[dict[str, Any]]:
    statuses = {t["task_id"]: effective_status(plan_slug, t) for t in plan["tasks"]}
    wave = []
    for task in plan["tasks"]:
        if statuses[task["task_id"]] != "planned":
            continue
        deps = task.get("depends_on", [])
        if all(statuses.get(dep) == "done" for dep in deps):
            wave.append(task)
    return wave


def not_done(plan_slug: str, plan: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for t in plan["tasks"]:
        status = effective_status(plan_slug, t)
        if status not in ("done", "failed"):
            result.append({**t, "status": status})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="plan slug")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--task", help="return this one task's status")
    group.add_argument(
        "--not-done", action="store_true", help="list tasks not yet done/failed"
    )
    group.add_argument(
        "--ready", action="store_true", help="list the current ready wave"
    )
    group.add_argument(
        "--full", action="store_true", help="dump the whole plan (rarely needed)"
    )
    args = parser.parse_args()

    try:
        plan = load_plan(args.plan)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.full:
        print(json.dumps(plan, indent=2))
        return 0

    if args.task:
        task = next((t for t in plan["tasks"] if t["task_id"] == args.task), None)
        if task is None:
            print(f"error: no task {args.task!r} in plan {args.plan!r}", file=sys.stderr)
            return 1
        print(json.dumps({**task, "status": effective_status(args.plan, task)}, indent=2))
        return 0

    if args.not_done:
        print(json.dumps(not_done(args.plan, plan), indent=2))
        return 0

    if args.ready:
        print(json.dumps(ready_wave(args.plan, plan), indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
