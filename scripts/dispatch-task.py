#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Consolidates the pre/post-dispatch instruction-file bookkeeping.

Two phases, both operating on the same instruction file
(<home>/.straw-boss/dispatch/<app>--<slug>.json -- see
skills/dispatching-work/references/dispatch-mechanics.md):

  write   -- before launch. Generates a Claude session id plus immutable
             workflow contract, writes the pending instruction, and (for a plan
             task) marks plan.json's matching task dispatched.
  confirm -- after launch-dispatched-agent.py writes a matching receipt.
             Validates its contract/provider/pane/identity binding, flips the
             instruction to in-progress, and records receipt identities.

This script never launches an agent itself; the launch adapter owns provider
injection and herdr calls.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dispatch_state import (
    contract_path,
    dump_json,
    install_runtime_launcher,
    launch_receipt_path,
    load_json,
    render_dispatch_contract,
    sha256_text,
    straw_boss_root,
)
from dispatch_transport import resolve_endpoint, validate_current_sender


def instruction_path(app: str, slug: str) -> Path:
    return straw_boss_root() / "dispatch" / f"{app}--{slug}.json"


def plan_path(plan_slug: str) -> Path:
    return straw_boss_root() / "plans" / plan_slug / "plan.json"


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


def check_retryable_failed(
    plan_slug: str,
    task_id: str,
    *,
    app: str,
    new_slug: str,
    repo_root: str,
) -> None:
    _, task = load_plan_and_task(plan_slug, task_id)
    status_path = straw_boss_root() / "plans" / plan_slug / "status" / f"{task_id}.json"
    if task.get("status") != "failed" or not status_path.is_file():
        raise ValueError(f"task {task_id!r} is not a wrapped failed task")
    if load_json(status_path).get("status") != "failed":
        raise ValueError(f"task {task_id!r} has no terminal failed status to retry")
    for path in (straw_boss_root() / "dispatch").glob("*.json"):
        try:
            candidate = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if (
            candidate.get("plan_id") == f"p-{plan_slug}"
            and candidate.get("task_id") == task_id
        ):
            raise ValueError(
                f"task {task_id!r} still has live instruction {path}; wrap it up before retry"
            )
    archives: list[tuple[Path, dict[str, Any]]] = []
    for path in (straw_boss_root() / "dispatch" / "archive").glob("*.json"):
        try:
            candidate = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if (
            candidate.get("plan_id") == f"p-{plan_slug}"
            and candidate.get("task_id") == task_id
        ):
            archives.append((path, candidate))
    if not archives:
        raise ValueError(f"task {task_id!r} has no wrapped attempt to retry")
    archive_path, previous = max(archives, key=lambda item: item[0].stat().st_mtime_ns)
    if previous.get("app") != app:
        raise ValueError("a failed plan retry must use the wrapped attempt's app")
    previous_slug = archive_path.name.removeprefix(f"{app}--").removesuffix(".json")
    if previous_slug == new_slug:
        raise ValueError("a failed plan retry requires a fresh dispatch slug")
    if previous.get("mode") != "claude-p" or previous.get("agent_kind") != "claude":
        raise ValueError("the wrapped attempt was not headless Claude")
    previous_root = Path(str(previous.get("repo_root", ""))).resolve()
    requested_root = Path(repo_root).resolve()
    if requested_root != previous_root:
        raise ValueError("a failed plan retry must reuse the wrapped attempt's repo_root")
    if not requested_root.is_dir():
        raise ValueError(
            "the wrapped attempt's repo_root is gone; restore its worktree before retry"
        )


def mark_plan_task(plan_slug: str, task_id: str, status: str) -> None:
    plan, task = load_plan_and_task(plan_slug, task_id)
    task["status"] = status
    dump_json(plan_path(plan_slug), plan)


def normalize_coworker_writable_paths(
    repo_root: Path, writable_paths: list[str]
) -> list[str]:
    normalized: list[str] = []
    for value in writable_paths:
        candidate = Path(value)
        if not value.strip() or candidate.is_absolute():
            raise ValueError(f"coworker writable path must be repo-relative: {value!r}")
        resolved = (repo_root / candidate).resolve()
        if not resolved.is_relative_to(repo_root):
            raise ValueError(f"coworker writable path escapes repo_root: {value!r}")
        relative = resolved.relative_to(repo_root).as_posix()
        if relative == ".":
            raise ValueError("coworker writable path cannot be the entire repo_root")
        if relative not in normalized:
            normalized.append(relative)
    return normalized


def resolve_coworker_context(
    parent_instruction_path: str,
    repo_root: str,
    writable_paths: list[str],
) -> dict[str, Any]:
    parent_path = Path(parent_instruction_path).resolve()
    if not parent_path.is_file():
        raise ValueError(f"no parent worker instruction at {parent_path}")
    parent = load_json(parent_path)
    if parent.get("status") != "in-progress":
        raise ValueError("a coworker requires an in-progress parent worker")
    if parent.get("mode") != "herdr-pane":
        raise ValueError("a coworker requires an interactive herdr-pane parent")
    if parent.get("parent_instruction_path"):
        raise ValueError("a coworker cannot launch another coworker")

    parent_root = Path(str(parent.get("repo_root", ""))).resolve()
    requested_root = Path(repo_root).resolve()
    if not parent_root.is_dir() or requested_root != parent_root:
        raise ValueError("a coworker must use the parent worker's exact repo_root")

    validate_current_sender(resolve_endpoint(parent, "worker"))
    for path in (straw_boss_root() / "dispatch").glob("*.json"):
        if path.resolve() == parent_path:
            continue
        try:
            candidate = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if candidate.get("parent_instruction_path") == str(parent_path):
            raise ValueError(
                f"parent worker already has coworker instruction {path}; wrap it up first"
            )

    resolve_endpoint(parent, "main")
    return {
        "parent_instruction_path": str(parent_path),
        "main_agent_herdr_pane_id": str(parent["herdr_pane_id"]),
        "main_agent_session_id": parent.get("session_id"),
        "main_agent_herdr_terminal_id": parent.get("herdr_terminal_id"),
        "main_agent_kind": str(parent["agent_kind"]),
        "root_main_agent_herdr_pane_id": str(parent["main_agent_herdr_pane_id"]),
        "root_main_agent_session_id": parent.get("main_agent_session_id"),
        "root_main_agent_herdr_terminal_id": parent.get(
            "main_agent_herdr_terminal_id"
        ),
        "root_main_agent_kind": str(parent["main_agent_kind"]),
        "coworker_writable_paths": normalize_coworker_writable_paths(
            parent_root, writable_paths
        ),
    }


def write_instruction(
    app: str,
    slug: str,
    task: str,
    mode: str,
    repo_root: str,
    batch: str | None,
    plan_slug: str | None,
    task_id: str | None,
    role: str | None,
    agent_kind: str,
    main_agent_kind: str,
    agent_profile: str | None,
    agent_model: str | None,
    agent_effort: str | None,
    advisor_model: str | None,
    main_agent_pane_id: str | None,
    main_agent_session_id: str | None,
    main_agent_terminal_id: str | None,
    coworker_context: dict[str, Any] | None = None,
    retry_failed_plan_task: bool = False,
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
    if (
        mode == "herdr-pane"
        and main_agent_kind == "claude"
        and not main_agent_session_id
    ):
        raise ValueError("--main-agent-session-id is required for a Claude main agent")
    if (
        mode == "herdr-pane"
        and main_agent_kind == "codex"
        and not main_agent_terminal_id
    ):
        raise ValueError("--main-agent-terminal-id is required for a Codex main agent")
    if advisor_model is not None and agent_kind != "claude":
        raise ValueError(
            f"--advisor-model is supported only for Claude Code; agent kind {agent_kind!r} "
            "has no native advisor"
        )
    if retry_failed_plan_task and plan_slug is None:
        raise ValueError("--retry-failed-plan-task requires --plan and --task-id")
    if retry_failed_plan_task and (mode != "claude-p" or agent_kind != "claude"):
        raise ValueError(
            "--retry-failed-plan-task is only for a headless Claude attempt"
        )
    if plan_slug is not None:
        assert task_id is not None
        if retry_failed_plan_task:
            check_retryable_failed(
                plan_slug,
                task_id,
                app=app,
                new_slug=slug,
                repo_root=repo_root,
            )
        else:
            check_dispatchable(plan_slug, task_id)  # read-only -- must run before any write below

    install_runtime_launcher()
    session_id = str(uuid.uuid4()) if agent_kind == "claude" else None
    generated_contract_path = contract_path(path)
    contract = render_dispatch_contract(
        path, coworker_context, mode=mode, agent_kind=agent_kind
    )
    contract_digest = sha256_text(contract)
    payload: dict[str, Any] = {
        "app": app,
        "role": role,
        "task": task,
        "mode": mode,
        "batch": batch,
        "session_id": session_id,
        "agent_kind": agent_kind,
        "main_agent_kind": main_agent_kind,
        "agent_profile": agent_profile,
        "agent_model": agent_model,
        "agent_effort": agent_effort,
        "advisor_model": advisor_model,
        "herdr_pane_id": None,
        "herdr_tab_id": None,
        "herdr_terminal_id": None,
        "main_agent_herdr_pane_id": main_agent_pane_id,
        "main_agent_session_id": main_agent_session_id,
        "main_agent_herdr_terminal_id": main_agent_terminal_id,
        "contract_path": str(generated_contract_path),
        "contract_sha256": contract_digest,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": repo_root,
    }
    if plan_slug is not None:
        payload["plan_id"] = f"p-{plan_slug}"
        payload["task_id"] = task_id
    if coworker_context is not None:
        payload.update(coworker_context)

    path.parent.mkdir(parents=True, exist_ok=True)
    generated_contract_path.write_text(contract)
    dump_json(path, payload)

    if plan_slug is not None:
        assert task_id is not None
        if retry_failed_plan_task:
            (
                straw_boss_root()
                / "plans"
                / plan_slug
                / "status"
                / f"{task_id}.json"
            ).unlink()
        mark_plan_task(plan_slug, task_id, "dispatched")

    return {
        "session_id": session_id,
        "instruction_path": str(path),
        "contract_path": str(generated_contract_path),
        "contract_sha256": contract_digest,
    }


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
    if payload.get("mode") == "herdr-pane":
        receipt_path = launch_receipt_path(path)
        if not receipt_path.is_file():
            raise ValueError(
                f"no launch receipt at {receipt_path} -- start this dispatch through "
                "launch-dispatched-agent.py before confirming it"
            )
        receipt = load_json(receipt_path)
        receipt_instruction_path = receipt.get("instruction_path")
        if (
            not isinstance(receipt_instruction_path, str)
            or Path(receipt_instruction_path).resolve() != path.resolve()
        ):
            raise ValueError(
                f"launch receipt instruction_path={receipt_instruction_path!r} "
                f"does not match {str(path)!r}"
            )
        expected_receipt = {
            "contract_sha256": payload.get("contract_sha256"),
            "agent_kind": payload.get("agent_kind"),
        }
        for field, expected in expected_receipt.items():
            if receipt.get(field) != expected:
                raise ValueError(
                    f"launch receipt {field}={receipt.get(field)!r} does not match {expected!r}"
                )
        if pane_id is not None and receipt.get("pane_id") != pane_id:
            raise ValueError("launch receipt pane id does not match --pane-id")
        if tab_id is not None and receipt.get("tab_id") != tab_id:
            raise ValueError("launch receipt tab id does not match --tab-id")
        receipt_session_id = receipt.get("session_id")
        receipt_terminal_id = receipt.get("herdr_terminal_id")
        if payload.get("agent_kind") == "codex" and (
            not isinstance(receipt_terminal_id, str) or not receipt_terminal_id
        ):
            raise ValueError("launch receipt has no herdr terminal id")
        if observed_session_id is not None and receipt_session_id != observed_session_id:
            raise ValueError("launch receipt session id does not match --observed-session-id")
        pane_id = str(receipt["pane_id"])
        tab_id = receipt.get("tab_id")
        observed_session_id = (
            receipt_session_id if isinstance(receipt_session_id, str) else None
        )
        if isinstance(receipt_terminal_id, str) and receipt_terminal_id:
            payload["herdr_terminal_id"] = receipt_terminal_id

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
    elif payload["agent_kind"] == "claude":
        raise ValueError("Claude launch receipt has no session id")
    else:
        payload["session_id"] = None
    dump_json(path, payload)
    return {"instruction_path": str(path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)

    write_p = sub.add_parser("write", help="write the pending instruction file")
    write_p.add_argument("--app", required=True)
    write_p.add_argument("--slug", required=True, help="short slug for the filename")
    write_p.add_argument(
        "--task",
        required=True,
        help="user requirement, requested outcome, necessary hints, and known coordination facts",
    )
    write_p.add_argument("--mode", required=True, choices=["claude-p", "herdr-pane"])
    write_p.add_argument("--repo-root", required=True)
    write_p.add_argument("--batch", default=None)
    write_p.add_argument("--plan", default=None, help="plan slug, if this is a plan task")
    write_p.add_argument("--task-id", default=None, help="this task's task_id within the plan")
    write_p.add_argument(
        "--retry-failed-plan-task",
        action="store_true",
        help="replace one wrapped failed plan attempt after its user-owned answer is known",
    )
    write_p.add_argument(
        "--role",
        default=None,
        help="short workroom/role label (e.g. database, frontend, api) the caller already "
        "knows for this dispatch; the launcher derives the operator-visible agent name from "
        "this instead of --app when given",
    )
    write_p.add_argument(
        "--agent-kind",
        default="claude",
        choices=["claude", "codex"],
        help="which agent CLI runs this dispatch (default: claude); the caller resolves this "
        "from apps.json's agentKind / an explicit override before calling this script",
    )
    write_p.add_argument(
        "--main-agent-kind",
        default=None,
        choices=["claude", "codex"],
        help="which agent CLI runs the dispatching main agent; notification routing depends on "
        "the sender/receiver pair and must not be inferred from --agent-kind",
    )
    write_p.add_argument(
        "--agent-profile",
        default=None,
        help="provider-native named profile: Claude --agent or Codex --profile",
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
        "--advisor-model",
        default=None,
        help="Claude Code native advisor model for this session; unsupported by Codex",
    )
    write_p.add_argument(
        "--main-agent-pane-id",
        default=None,
        help="the dispatching main agent's own herdr pane id ($HERDR_PANE_ID), for herdr-pane mode -- "
        "used only by the script-owned transport; omit when the main agent has no live pane",
    )
    write_p.add_argument(
        "--main-agent-session-id",
        default=None,
        help="the dispatching Claude main agent's live herdr agent_session.value",
    )
    write_p.add_argument(
        "--main-agent-terminal-id",
        default=None,
        help="the dispatching Codex main agent's live herdr terminal_id",
    )
    write_p.add_argument(
        "--parent-instruction-path",
        default=None,
        help="current dispatched worker instruction; derives same-worktree coworker identity",
    )
    write_p.add_argument(
        "--writable-path",
        action="append",
        default=[],
        help="repo-relative coworker write scope; omit for review-only",
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
            coworker_context = None
            if args.parent_instruction_path is not None:
                if args.mode != "herdr-pane" or args.plan is not None or args.batch is not None:
                    raise ValueError(
                        "a coworker is one standalone herdr-pane dispatch, not a Plan or batch"
                    )
                coworker_context = resolve_coworker_context(
                    args.parent_instruction_path,
                    args.repo_root,
                    args.writable_path,
                )
                args.main_agent_kind = coworker_context["main_agent_kind"]
                args.main_agent_pane_id = coworker_context[
                    "main_agent_herdr_pane_id"
                ]
                args.main_agent_session_id = coworker_context[
                    "main_agent_session_id"
                ]
                args.main_agent_terminal_id = coworker_context[
                    "main_agent_herdr_terminal_id"
                ]
            elif args.main_agent_kind is None:
                raise ValueError("--main-agent-kind is required for a top-level dispatch")
            result = write_instruction(
                app=args.app,
                slug=args.slug,
                task=args.task,
                mode=args.mode,
                repo_root=args.repo_root,
                batch=args.batch,
                plan_slug=args.plan,
                task_id=args.task_id,
                role=args.role,
                agent_kind=args.agent_kind,
                main_agent_kind=args.main_agent_kind,
                agent_profile=args.agent_profile,
                agent_model=args.agent_model,
                agent_effort=args.agent_effort,
                advisor_model=args.advisor_model,
                main_agent_pane_id=args.main_agent_pane_id,
                main_agent_session_id=args.main_agent_session_id,
                main_agent_terminal_id=args.main_agent_terminal_id,
                coworker_context=coworker_context,
                retry_failed_plan_task=args.retry_failed_plan_task,
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
