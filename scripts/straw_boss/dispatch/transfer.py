"""Move a dispatch's coordinator route to another main agent.

Design: docs/specs/2026-09-18-cross-orchestrator-dispatch-transfer/design.md.

A route is the four fields every main-side command validates against. It moves
through an orchestrator handoff, which the source offers and the receiver
accepts, or through a takeover the user asked for. Both check every listed
dispatch before writing any, prove the new route against the live receiver,
and carry a coworker's root route along with its parent.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from straw_boss.dispatch.state import (
    INSTRUCTION_SIBLING_SUFFIXES,
    dump_json,
    load_json,
    straw_boss_root,
)
from straw_boss.herdr.session import (
    HerdrCommandError,
    HerdrUnavailableError,
    resolve_endpoint,
    validate_current_process_in_pane,
    validate_current_sender,
    validate_live_session,
)
from straw_boss.orchestrator import agent_identity, current_agent, live_agents


ROUTE_FIELDS = ("herdr_pane_id", "session_id", "herdr_terminal_id", "kind")
MAIN = "main_agent_"
ROOT_MAIN = "root_main_agent_"


def route_of(instruction: dict[str, Any], prefix: str) -> dict[str, Any]:
    return {field: instruction.get(f"{prefix}{field}") for field in ROUTE_FIELDS}


def with_route(
    instruction: dict[str, Any], prefix: str, route: dict[str, Any]
) -> dict[str, Any]:
    return {**instruction, **{f"{prefix}{field}": route[field] for field in ROUTE_FIELDS}}


def caller_route() -> dict[str, Any]:
    """The route of the main agent running this command, proven from its pane."""
    pane_id = os.environ.get("HERDR_PANE_ID")
    if not pane_id:
        raise ValueError("moving a dispatch route needs HERDR_PANE_ID; run it from the coordinator's pane")
    validate_current_process_in_pane(pane_id)
    kind, session, terminal = agent_identity(current_agent(live_agents()))
    return {"herdr_pane_id": pane_id, "session_id": session, "herdr_terminal_id": terminal, "kind": kind}


def dispatch_instructions() -> list[tuple[Path, dict[str, Any]]]:
    found = []
    for path in sorted((straw_boss_root() / "dispatch").glob("*.json")):
        if path.name.endswith(INSTRUCTION_SIBLING_SUFFIXES):
            continue
        try:
            instruction = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(instruction, dict) and "task" in instruction:
            found.append((path.resolve(), instruction))
    return found


def load_movable(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"no instruction file at {path}")
    instruction = load_json(path)
    if instruction.get("mode") != "herdr-pane":
        raise ValueError(f"{path} is not an interactive herdr-pane dispatch")
    if instruction.get("parent_instruction_path"):
        raise ValueError(f"{path} is a coworker; it moves with its parent dispatch")
    if instruction.get("status") != "in-progress":
        raise ValueError(
            f"{path} is {instruction.get('status')!r}; only an in-progress dispatch moves, "
            "and its own coordinator launches or wraps up a pending one"
        )
    return instruction


def owns(instruction: dict[str, Any]) -> bool:
    """Whether the live session in the recorded main pane is the recorded one.

    Only Herdr's answer decides; no answer at all propagates, so an outage
    cannot pass a dispatch off as someone else's and let the source pane close.
    """
    try:
        validate_live_session(resolve_endpoint(instruction, "main"))
    except HerdrUnavailableError:
        raise
    except HerdrCommandError as exc:
        if exc.error_code in {"agent_not_found", "pane_not_found"}:
            return False
        raise
    except ValueError:
        return False
    return True


def offer_dispatches(
    paths: list[str], *, source_pane_id: str, retains_scope: bool
) -> list[dict[str, Any]]:
    """Snapshot the dispatches a handoff offers, proven owned by the caller."""
    listed = list(dict.fromkeys(Path(path).resolve() for path in paths))
    snapshots = []
    for path in listed:
        instruction = load_movable(path)
        validate_current_sender(resolve_endpoint(instruction, "main"))
        snapshots.append({"instruction_path": str(path), "route": route_of(instruction, MAIN)})
    if not retains_scope:
        unlisted = [
            str(path)
            for path, instruction in dispatch_instructions()
            if path not in listed
            and instruction.get("mode") == "herdr-pane"
            and not instruction.get("parent_instruction_path")
            and instruction.get("status") == "in-progress"
            and instruction.get(f"{MAIN}herdr_pane_id") == source_pane_id
            and owns(instruction)
        ]
        if unlisted:
            raise ValueError(
                "this handoff retains nothing, so the source pane closes, but it still "
                "coordinates dispatches the handoff does not list; pass --dispatch for each "
                f"or --retains for the work that stays: {', '.join(unlisted)}"
            )
    return snapshots


def move_main_routes(
    moves: list[tuple[Path, dict[str, Any] | None]],
    new_route: dict[str, Any],
    *,
    reason: str,
    evidence: dict[str, Any],
) -> dict[str, list[Any]]:
    """Point each listed dispatch's main route at `new_route`.

    An expected route is the offer snapshot: the dispatch must still carry it,
    or already carry `new_route` from an earlier acceptance. Without one, the
    dispatch must not already route to `new_route`. Every dispatch is checked,
    and the new route proven live, before any file is written.
    """
    pending: list[tuple[Path, dict[str, Any]]] = []
    already: list[str] = []
    seen: set[Path] = set()
    for listed, expected in moves:
        path = listed.resolve()
        if path in seen:
            continue
        seen.add(path)
        instruction = load_movable(path)
        current = route_of(instruction, MAIN)
        if current == new_route:
            if expected is None:
                raise ValueError(f"{path} already routes to this coordinator")
            already.append(str(path))
            continue
        if expected is not None and current != expected:
            raise ValueError(
                f"{path} no longer carries the route the handoff offered; "
                "ownership stays with the source"
            )
        pending.append((path, instruction))
    if not pending:
        return {"moved": [], "already": already}

    validate_live_session(resolve_endpoint(with_route(pending[0][1], MAIN, new_route), "main"))

    coworkers = dispatch_instructions()
    moved = []
    at = datetime.now(timezone.utc).isoformat()
    for path, instruction in pending:
        if load_json(path) != instruction:
            raise ValueError(f"{path} changed during the move; retry from fresh state")
        before = route_of(instruction, MAIN)
        entry = {"at": at, "reason": reason, "before": before, "after": new_route, "evidence": evidence}
        dump_json(path, {
            **with_route(instruction, MAIN, new_route),
            "main_agent_transfers": [*instruction.get("main_agent_transfers", []), entry],
        })
        for coworker_path, coworker in coworkers:
            if (coworker.get("parent_instruction_path") != str(path)
                    or route_of(coworker, ROOT_MAIN) != before):
                continue
            dump_json(coworker_path, {
                **with_route(coworker, ROOT_MAIN, new_route),
                "root_main_agent_transfers": [
                    *coworker.get("root_main_agent_transfers", []), entry,
                ],
            })
        moved.append({"instruction_path": str(path), "before": before})
    return {"moved": moved, "already": already}
