#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Consolidates the pre/post-dispatch instruction-file bookkeeping.

Two phases, both operating on the same instruction file
(<home>/.straw-boss/dispatch/<app>--<slug>.json -- see
skills/dispatching-work/references/dispatch-mechanics.md):

  write   -- before the actual claude/herdr dispatch call. Generates a
             session_id, writes the instruction file with status
             "pending", and (for a plan task) marks plan.json's matching
             task "dispatched". Does not run any claude/herdr command
             itself -- the caller still does that, using the session_id
             this prints.
  confirm -- after the dispatch call succeeds and delivery is confirmed.
             Flips the instruction to "in-progress" and records
             herdr_pane_id/herdr_tab_id for herdr-pane mode.

This script never runs claude/herdr/git itself -- those stay live tool
calls the orchestrator makes per dispatch-mechanics.md, so their output
and failures stay visible. This script only keeps the bookkeeping files
consistent around them.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def mp_dev_root() -> Path:
    return Path.home() / ".straw-boss"


def instruction_path(app: str, slug: str) -> Path:
    return mp_dev_root() / "dispatch" / f"{app}--{slug}.json"


def plan_path(plan_slug: str) -> Path:
    return mp_dev_root() / "plans" / plan_slug / "plan.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


def load_plan_and_task(plan_slug: str, task_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    path = plan_path(plan_slug)
    if not path.is_file():
        raise ValueError(f"no plan found at {path}")
    plan = load_json(path)
    task = next((t for t in plan["tasks"] if t["task_id"] == task_id), None)
    if task is None:
        raise ValueError(f"no task {task_id!r} in plan {plan_slug!r}")
    return plan, task


def check_dispatchable(plan_slug: str, task_id: str) -> None:
    """Read-only guard, checked before any file is written -- a rejected
    dispatch must never leave a stray instruction file behind."""
    _, task = load_plan_and_task(plan_slug, task_id)
    if task["status"] != "planned":
        raise ValueError(f"task {task_id!r} is already {task['status']!r} -- refusing to dispatch it again")


def mark_plan_task(plan_slug: str, task_id: str, status: str) -> None:
    plan, task = load_plan_and_task(plan_slug, task_id)
    task["status"] = status
    dump_json(plan_path(plan_slug), plan)


def write_instruction(
    app: str,
    slug: str,
    task: str,
    mode: str,
    repo_root: str,
    batch: str | None,
    plan_slug: str | None,
    task_id: str | None,
    agent_kind: str,
    main_agent_kind: str,
    agent_model: str | None,
    agent_effort: str | None,
    main_agent_pane_id: str | None,
    main_agent_peer_name: str | None,
) -> dict[str, Any]:
    path = instruction_path(app, slug)
    if path.exists():
        raise ValueError(
            f"instruction file {path} already exists -- pick a different --slug or wrap up the existing dispatch first"
        )
    if (plan_slug is None) != (task_id is None):
        raise ValueError("--plan and --task-id must be given together, or not at all")
    if mode == "herdr-pane" and not main_agent_pane_id:
        raise ValueError("--main-agent-pane-id is required for herdr-pane mode")
    both_claude = agent_kind == "claude" and main_agent_kind == "claude"
    if main_agent_peer_name and not both_claude:
        raise ValueError(
            "--main-agent-peer-name is only valid when both agent kinds are 'claude'"
        )
    if mode == "claude-p" and both_claude and not main_agent_peer_name:
        raise ValueError(
            "--main-agent-peer-name is required for a headless Claude-to-Claude dispatch"
        )
    if plan_slug is not None:
        assert task_id is not None
        check_dispatchable(plan_slug, task_id)  # read-only -- must run before any write below

    session_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "app": app,
        "task": task,
        "mode": mode,
        "batch": batch,
        "session_id": session_id,
        "agent_kind": agent_kind,
        "main_agent_kind": main_agent_kind,
        "agent_model": agent_model,
        "agent_effort": agent_effort,
        "herdr_pane_id": None,
        "herdr_tab_id": None,
        "main_agent_herdr_pane_id": main_agent_pane_id,
        "main_agent_send_message_peer": main_agent_peer_name,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": repo_root,
    }
    if plan_slug is not None:
        payload["plan_id"] = f"p-{plan_slug}"
        payload["task_id"] = task_id

    path.parent.mkdir(parents=True, exist_ok=True)
    dump_json(path, payload)

    if plan_slug is not None:
        assert task_id is not None
        mark_plan_task(plan_slug, task_id, "dispatched")

    return {"session_id": session_id, "instruction_path": str(path)}


def confirm_instruction(
    app: str,
    slug: str,
    pane_id: str | None,
    tab_id: str | None,
    observed_session_id: str | None,
) -> dict[str, Any]:
    path = instruction_path(app, slug)
    if not path.is_file():
        raise ValueError(f"no instruction file at {path}")
    payload = load_json(path)
    if payload["status"] != "pending":
        raise ValueError(
            f"instruction at {path} is {payload['status']!r}, not 'pending' -- "
            f"refusing to confirm a dispatch that wasn't just written"
        )
    payload["status"] = "in-progress"
    if pane_id is not None:
        payload["herdr_pane_id"] = pane_id
    if tab_id is not None:
        payload["herdr_tab_id"] = tab_id
    if observed_session_id is not None:
        # claude was launched with the pre-generated session_id passed as
        # --session-id, so the two must match -- a mismatch means the pane
        # this confirms isn't the one this dispatch launched. Other agent
        # kinds (e.g. codex) don't accept a caller-supplied session id -- the
        # pre-generated one was never passed to the launch command, so it's
        # replaced with what the agent itself reported instead of compared.
        if payload["agent_kind"] == "claude" and payload["session_id"] != observed_session_id:
            raise ValueError(
                f"observed session id {observed_session_id!r} does not match the session id "
                f"{payload['session_id']!r} recorded at write time -- the agent in this pane may "
                f"not be the one this dispatch launched"
            )
        payload["session_id"] = observed_session_id
    dump_json(path, payload)
    return {"instruction_path": str(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)

    write_p = sub.add_parser("write", help="write the pending instruction file")
    write_p.add_argument("--app", required=True)
    write_p.add_argument("--slug", required=True, help="short slug for the filename")
    write_p.add_argument("--task", required=True, help="full task text for the dispatched session")
    write_p.add_argument("--mode", required=True, choices=["claude-p", "herdr-pane"])
    write_p.add_argument("--repo-root", required=True)
    write_p.add_argument("--batch", default=None)
    write_p.add_argument("--plan", default=None, help="plan slug, if this is a plan task")
    write_p.add_argument("--task-id", default=None, help="this task's task_id within the plan")
    write_p.add_argument(
        "--agent-kind",
        default="claude",
        choices=["claude", "codex"],
        help="which agent CLI runs this dispatch (default: claude); the caller resolves this "
        "from apps.json's agentKind / an explicit override before calling this script",
    )
    write_p.add_argument(
        "--main-agent-kind",
        required=True,
        choices=["claude", "codex"],
        help="which agent CLI runs the dispatching main agent; notification routing depends on "
        "the sender/receiver pair and must not be inferred from --agent-kind",
    )
    write_p.add_argument(
        "--agent-model", default=None, help="model override to record, if the caller chose one for this dispatch"
    )
    write_p.add_argument(
        "--agent-effort",
        default=None,
        help="reasoning-effort override to record, if the caller chose one for this dispatch",
    )
    write_p.add_argument(
        "--main-agent-pane-id",
        default=None,
        help="the dispatching main agent's own herdr pane id ($HERDR_PANE_ID), for herdr-pane mode -- "
        "lets the dispatched agent look up its main agent's reachability via get-main-agent.py "
        "instead of relying only on prose stated in --task; omit for claude-p (no live pane)",
    )
    write_p.add_argument(
        "--main-agent-peer-name",
        default=None,
        help="the SendMessage peer name this main agent actually resolved for itself; valid only "
        "when both --agent-kind and --main-agent-kind are claude, and required for that pair when "
        "no herdr pane is used -- its own "
        "claude --name <value> launch flag if it was started with one (detect it from this "
        "session's own process args, e.g. via ps -p $CLAUDE_PID -ww -o args=), otherwise the "
        "per-session-unique value from an explicit /rename call (see cross-session-coordination.md's "
        "'Making the main agent addressable'); required with no default -- two concurrent main "
        "agents both silently falling back to the same bare literal is a real SendMessage delivery "
        "hazard, confirmed to have actually happened",
    )

    confirm_p = sub.add_parser("confirm", help="mark the dispatch in-progress after it lands")
    confirm_p.add_argument("--app", required=True)
    confirm_p.add_argument("--slug", required=True)
    confirm_p.add_argument("--pane-id", default=None)
    confirm_p.add_argument("--tab-id", default=None)
    confirm_p.add_argument(
        "--observed-session-id",
        default=None,
        help="session id reported back by the launched agent, for a kind that can't pre-assign one",
    )

    args = parser.parse_args()

    try:
        if args.action == "write":
            result = write_instruction(
                app=args.app,
                slug=args.slug,
                task=args.task,
                mode=args.mode,
                repo_root=args.repo_root,
                batch=args.batch,
                plan_slug=args.plan,
                task_id=args.task_id,
                agent_kind=args.agent_kind,
                main_agent_kind=args.main_agent_kind,
                agent_model=args.agent_model,
                agent_effort=args.agent_effort,
                main_agent_pane_id=args.main_agent_pane_id,
                main_agent_peer_name=args.main_agent_peer_name,
            )
        else:
            result = confirm_instruction(
                app=args.app,
                slug=args.slug,
                pane_id=args.pane_id,
                tab_id=args.tab_id,
                observed_session_id=args.observed_session_id,
            )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
