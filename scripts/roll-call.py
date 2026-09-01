#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Reconcile live herdr agents against ~/.straw-boss/dispatch/ instructions.

Read-only: it starts nothing, closes nothing, and writes nothing. It answers
the question no other script can -- which workers are actually alive right now,
whose they are, and which dispatch records no longer have anyone behind them --
so several coordinators sharing one herdr session can each recognise their own.

**Liveness is decided by `agent_session.value` (Claude) or `terminal_id`
(Codex) together with `agent_status`, never by a pane's terminal title.** A
title only reflects whatever the foreground program last set: an idle agent's
pane can read back as a plain shell prompt while the agent is perfectly alive.
Reading a title as proof of death is what let one coordinator declare another's
live worker an orphan and dispatch the same task a second time.

**A live agent with no instruction is not evidence of an ownerless pane.** A
coordinator's own pane never has an instruction of its own, and a worker pane
that has just been split is in the window before `dispatch-task.py write` runs.
Both appear here as `unattributed`, which means "not attributable from this
data", not "free to close".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dispatch_state import (
    launch_failure_path,
    load_json,
    resolve_instruction_status_path,
    straw_boss_root,
)
from dispatch_transport import run_herdr


TERMINAL_STATUSES = frozenset({"done", "failed", "cancelled"})
# Files that share an instruction's <app>--<slug> stem and match a naive
# *.json glob without being instructions themselves.
INSTRUCTION_SIBLING_SUFFIXES = (
    ".launch.json",
    ".launch-failure.json",
    ".status.json",
)


def instruction_paths() -> list[Path]:
    directory = straw_boss_root() / "dispatch"
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.glob("*.json")
        if not path.name.endswith(INSTRUCTION_SIBLING_SUFFIXES)
    )


def session_value(agent: dict[str, Any]) -> str | None:
    session = agent.get("agent_session")
    value = session.get("value") if isinstance(session, dict) else None
    return value if isinstance(value, str) and value else None


def live_agents() -> list[dict[str, Any]]:
    payload = run_herdr(["agent", "list"])
    agents = payload.get("result", {}).get("agents")
    if not isinstance(agents, list):
        raise ValueError("herdr agent list did not return an agent list")
    return [agent for agent in agents if isinstance(agent, dict)]


def open_pane_ids() -> set[str]:
    """Panes herdr still has, agent or not -- a pane outliving its agent is the
    'nobody closed it' case, which is different from a pane that is gone."""
    payload = run_herdr(["pane", "list"])
    panes = payload.get("result", {}).get("panes")
    if not isinstance(panes, list):
        return set()
    return {
        str(pane["pane_id"])
        for pane in panes
        if isinstance(pane, dict) and pane.get("pane_id")
    }


def worker_agent(
    instruction: dict[str, Any],
    by_session: dict[str, dict[str, Any]],
    by_terminal: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """The live agent this instruction's worker endpoint identifies, if any.

    Matched on the provider fingerprint rather than the recorded pane id: a
    closed pane's id can be handed to somebody else's agent later, and matching
    on it would report a stranger as this dispatch's worker.
    """
    if instruction.get("agent_kind") == "codex":
        terminal_id = instruction.get("herdr_terminal_id")
        return by_terminal.get(str(terminal_id)) if terminal_id else None
    session_id = instruction.get("session_id")
    return by_session.get(str(session_id)) if session_id else None


def reported_status(instruction_path: Path, instruction: dict[str, Any]) -> str | None:
    path = resolve_instruction_status_path(instruction_path, instruction)
    if not path.is_file():
        return None
    try:
        return str(load_json(path).get("status"))
    except (OSError, json.JSONDecodeError):
        return None


def launch_failure_summary(instruction_path: Path) -> str | None:
    path = launch_failure_path(instruction_path)
    if not path.is_file():
        return None
    try:
        attempts = load_json(path).get("attempts")
    except (OSError, json.JSONDecodeError):
        return f"unreadable launch-failure record at {path}"
    if not isinstance(attempts, list) or not attempts:
        return f"launch-failure record at {path}"
    last = attempts[-1]
    error = last.get("error") if isinstance(last, dict) else None
    first_line = str(error).splitlines()[0] if error else "no error recorded"
    return f"launch failed {len(attempts)}x: {first_line}"


def classify(
    instruction: dict[str, Any],
    agent: dict[str, Any] | None,
    reported: str | None,
    pane_open: bool,
) -> tuple[str, str]:
    """Verdict plus the one thing the reader needs to do about it."""
    if instruction.get("status") == "pending":
        if agent is not None:
            # A launch that started an agent but never reached
            # `dispatch-task.py confirm`. Reading the instruction alone would
            # call this never-launched and invite a second dispatch on top of a
            # worker that is already doing the job.
            return (
                "launched-unconfirmed",
                "an agent carries this instruction's fingerprint but "
                "dispatch-task.py confirm never recorded it",
            )
        return "never-launched", "no agent was ever confirmed for this instruction"
    if reported in TERMINAL_STATUSES:
        if agent is not None:
            return "awaiting-collection", f"reported {reported}; its pane is still open"
        if pane_open:
            return "awaiting-collection", f"reported {reported}; agent gone, pane still open"
        return "awaiting-collection", f"reported {reported}; pane already gone"
    if agent is None:
        return (
            "orphaned",
            "no live agent carries this worker's session; recover-task-status.py "
            "writes the terminal status before wrap-up",
        )
    if reported:
        return "checkpoint", f"waiting at {reported}"
    return "running", f"agent_status={agent.get('agent_status')}"


def build_report(mine_session: str | None) -> dict[str, Any]:
    agents = live_agents()
    panes = open_pane_ids()
    by_session = {
        value: agent for agent in agents if (value := session_value(agent)) is not None
    }
    by_terminal = {
        str(agent["terminal_id"]): agent
        for agent in agents
        if isinstance(agent.get("terminal_id"), str) and agent["terminal_id"]
    }

    rows: list[dict[str, Any]] = []
    claimed_panes: set[str] = set()
    coordinator_sessions: set[str] = set()

    # Every instruction is read, whatever --mine asks for: a worker or
    # coordinator belonging to another session must still be attributed, or
    # filtering the report would manufacture exactly the ownerless-looking
    # agent this script exists to stop anyone acting on.
    for path in instruction_paths():
        try:
            instruction = load_json(path)
        except (OSError, json.JSONDecodeError):
            rows.append(
                {
                    "dispatch": path.stem,
                    "verdict": "unreadable",
                    "mine": True,
                    "note": f"could not parse {path}",
                    "instruction_path": str(path),
                }
            )
            continue
        main_session = instruction.get("main_agent_session_id")
        if main_session:
            coordinator_sessions.add(str(main_session))

        agent = worker_agent(instruction, by_session, by_terminal)
        recorded_pane = instruction.get("herdr_pane_id")
        reported = reported_status(path, instruction)
        pane_open = bool(recorded_pane) and str(recorded_pane) in panes
        verdict, note = classify(instruction, agent, reported, pane_open)
        if agent is not None:
            claimed_panes.add(str(agent.get("pane_id")))
        if verdict in ("never-launched", "launched-unconfirmed"):
            failure = launch_failure_summary(path)
            if failure:
                note = failure

        live_pane = str(agent.get("pane_id")) if agent else None
        if agent is not None and recorded_pane and live_pane != str(recorded_pane):
            note = f"{note}; worker moved to pane {live_pane} (instruction records {recorded_pane})"
        if main_session and str(main_session) not in by_session:
            note = f"{note}; its coordinator session is no longer live"

        rows.append(
            {
                "dispatch": path.stem,
                "verdict": verdict,
                "mine": mine_session is None or str(main_session) == mine_session,
                "app": instruction.get("app"),
                "role": instruction.get("role"),
                "agent_kind": instruction.get("agent_kind"),
                "instruction_status": instruction.get("status"),
                "reported_status": reported,
                "worker_pane": live_pane or recorded_pane,
                "worker_agent_status": agent.get("agent_status") if agent else None,
                "worker_name": agent.get("name") if agent else None,
                "coordinator_pane": instruction.get("main_agent_herdr_pane_id"),
                "coordinator_session": main_session,
                "note": note,
                "instruction_path": str(path),
            }
        )

    unattributed: list[dict[str, Any]] = []
    for agent in agents:
        pane_id = str(agent.get("pane_id"))
        if pane_id in claimed_panes:
            continue
        value = session_value(agent)
        role = (
            "coordinator"
            if value is not None and value in coordinator_sessions
            else "unattributed"
        )
        unattributed.append(
            {
                "pane_id": pane_id,
                "role": role,
                "agent": agent.get("agent"),
                "agent_status": agent.get("agent_status"),
                "name": agent.get("name"),
                "session": value,
                "cwd": agent.get("cwd"),
            }
        )

    return {
        "dispatches": [row for row in rows if row["mine"]],
        "agents_without_instruction": unattributed,
    }


def render(report: dict[str, Any]) -> str:
    lines: list[str] = []
    rows = report["dispatches"]
    lines.append(f"dispatches ({len(rows)})")
    if not rows:
        lines.append("  none")
    for row in sorted(rows, key=lambda r: (r["verdict"], r["dispatch"])):
        worker = row.get("worker_pane") or "-"
        status = row.get("worker_agent_status") or "no live agent"
        lines.append(
            f"  [{row['verdict']}] {row['dispatch']}\n"
            f"      worker {worker} ({status})"
            f"  coordinator {row.get('coordinator_pane') or '-'}"
            f" {str(row.get('coordinator_session') or '-')[:8]}\n"
            f"      {row['note']}"
        )

    extras = report["agents_without_instruction"]
    lines.append("")
    lines.append(f"live agents with no instruction of their own ({len(extras)})")
    lines.append(
        "  a coordinator has none by design, and a just-split worker pane has none yet:"
    )
    lines.append("  never read this section as permission to close a pane.")
    if not extras:
        lines.append("  none")
    for agent in sorted(extras, key=lambda a: (a["role"], a["pane_id"])):
        lines.append(
            f"  [{agent['role']}] {agent['pane_id']} ({agent['agent_status']})"
            f"  {agent.get('name') or '-'}  {agent.get('cwd') or '-'}"
        )
    return "\n".join(lines)


def current_session() -> str | None:
    pane_id = os.environ.get("HERDR_PANE_ID")
    if not pane_id:
        raise ValueError("--mine needs HERDR_PANE_ID; run it from inside a herdr pane")
    for agent in live_agents():
        if str(agent.get("pane_id")) == pane_id:
            return session_value(agent)
    raise ValueError(f"herdr has no live agent in pane {pane_id!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the raw report")
    parser.add_argument(
        "--mine",
        action="store_true",
        help="only dispatches this pane's session dispatched, for a machine "
        "running several coordinators at once",
    )
    args = parser.parse_args()

    try:
        report = build_report(current_session() if args.mine else None)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
