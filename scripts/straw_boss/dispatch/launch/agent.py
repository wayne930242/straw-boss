"""The herdr agent running in a worker pane: identity, readiness, gates."""

from __future__ import annotations

import os
from time import monotonic, sleep
from typing import Any

from straw_boss.dispatch.launch.pane import pane_excerpt
from straw_boss.herdr.session import session_value
from straw_boss.herdr.transport import (
    HerdrCommandError,
    normalize_transcript_text,
    run_herdr,
)
from straw_boss.naming import derive_agent_name, unique_agent_name


AGENT_SESSION_WAIT_SECONDS = 15.0

AGENT_START_PANE_READY_TIMEOUT_SECONDS = 5.0

AGENT_START_PANE_READY_POLL_INTERVAL_SECONDS = 0.25

# `agent start` returns as soon as herdr can see the agent, which is not yet the
# same as the agent being able to turn input into a turn: a Claude first-run
# gate is reported idle/interactive_ready for about a second before herdr
# reclassifies it blocked. herdr's own `agent wait --until idle --until
# blocked` cannot express this -- it returns instantly on that same idle -- so
# the reading is held open for a short window instead.
AGENT_SETTLE_WINDOW_SECONDS = 4.0

AGENT_SETTLE_POLL_INTERVAL_SECONDS = 0.5

# The option a Claude Code startup gate preselects. Its presence on the pane is
# the unambiguous sign that submitting anything there exits the worker,
# whatever status herdr has settled on for the gate so far. Matched
# whitespace-normalized, because a narrow worker pane wraps the surrounding
# text.
STARTUP_GATE_PANE_MARKER = "No, exit"

DEPRECATED_ORCHESTRATOR_NAME_MARKER = "straw-boss-orchestrator"

def live_agent(pane_id: str) -> dict[str, object]:
    payload = run_herdr(["agent", "get", pane_id])
    agent = payload.get("result", {}).get("agent")
    if not isinstance(agent, dict):
        raise ValueError(f"herdr could not resolve the launched agent in pane {pane_id!r}")
    return agent

def live_agent_identity(pane_id: str, agent_kind: str) -> tuple[str, str | None]:
    agent = live_agent(pane_id)
    if agent.get("pane_id") != pane_id:
        raise ValueError(f"launched agent did not report pane {pane_id!r}")
    if agent.get("agent") != agent_kind:
        raise ValueError(
            f"launched agent in pane {pane_id!r} reported kind {agent.get('agent')!r}, "
            f"expected {agent_kind!r}"
        )
    terminal_id = agent.get("terminal_id")
    if not isinstance(terminal_id, str) or not terminal_id:
        raise ValueError(f"launched agent in pane {pane_id!r} did not expose terminal_id")
    return terminal_id, session_value(agent)

def ensure_coordinator_named(instruction: dict[str, object], taken: set[str]) -> None:
    """Give the coordinator's own pane an operator-visible name, once.

    Runs only for a top-level dispatch (never a coworker's, whose "main pane"
    is a fellow worker, not the coordinator) and only while that pane is still
    unnamed -- an existing name, however it got there, is left alone.
    """
    main_pane_id = instruction.get("main_agent_herdr_pane_id")
    if not isinstance(main_pane_id, str) or not main_pane_id:
        raise ValueError("dispatch instruction has no main-agent herdr pane")
    if live_agent(main_pane_id).get("name"):
        return
    candidate = unique_agent_name(
        derive_agent_name("coordinator", str(instruction["app"])), taken
    )
    run_herdr(["agent", "rename", main_pane_id, candidate])
    taken.add(candidate)

def decoy_orchestrator_panes(
    payload: dict[str, Any], exclude_pane_ids: set[str]
) -> list[str]:
    """Live panes still carrying the retired `straw-boss-orchestrator*` label.

    That convention had a coordinator run `/rename straw-boss-orchestrator` on
    its own pane; nothing ever clears the name or terminal title it left
    behind once a session ends, so an idle pane from months ago keeps reading
    as *the* orchestrator to anything that goes looking for one by name
    pattern instead of by the pane id a dispatch instruction actually records.
    """
    try:
        agents = payload["result"]["agents"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unexpected 'herdr agent list' shape -- missing {exc}") from exc
    if not isinstance(agents, list):
        raise ValueError(f"unexpected 'herdr agent list' shape -- agents was {type(agents).__name__}")
    decoys: list[str] = []
    for agent in agents:
        if not isinstance(agent, dict) or agent.get("pane_id") in exclude_pane_ids:
            continue
        fields = (agent.get("name"), agent.get("terminal_title"), agent.get("terminal_title_stripped"))
        if any(
            isinstance(value, str) and DEPRECATED_ORCHESTRATOR_NAME_MARKER in value.lower()
            for value in fields
        ):
            decoys.append(str(agent.get("pane_id") or "<unknown pane>"))
    return decoys

def decoy_orchestrator_warning(
    payload: dict[str, Any], exclude_pane_ids: set[str]
) -> str | None:
    decoys = decoy_orchestrator_panes(payload, exclude_pane_ids)
    if not decoys:
        return None
    return (
        f"pane(s) {', '.join(sorted(decoys))} still carry the retired "
        f"'{DEPRECATED_ORCHESTRATOR_NAME_MARKER}*' naming convention; they are not this "
        "dispatch's main agent, whatever they look like -- do not treat them as one"
    )

def agent_session_wait_seconds() -> float:
    raw = os.environ.get("STRAW_BOSS_AGENT_SESSION_WAIT_SECONDS")
    if raw is None:
        return AGENT_SESSION_WAIT_SECONDS
    try:
        parsed = float(raw)
    except ValueError:
        return AGENT_SESSION_WAIT_SECONDS
    return parsed if parsed >= 0 else AGENT_SESSION_WAIT_SECONDS

def wait_for_agent_session(
    pane_id: str,
    *,
    timeout_seconds: float | None = None,
    poll_interval_seconds: float = 0.25,
    required: bool = True,
) -> str | None:
    if timeout_seconds is None:
        timeout_seconds = agent_session_wait_seconds()
    deadline = monotonic() + timeout_seconds
    last_status: object = None
    while True:
        agent = live_agent(pane_id)
        last_status = agent.get("agent_status")
        session = agent.get("agent_session")
        if isinstance(session, dict):
            value = session.get("value")
            if isinstance(value, str) and value:
                return value
        remaining = deadline - monotonic()
        if remaining <= 0:
            if not required:
                return None
            raise ValueError(
                "launched agent did not expose agent_session.value within "
                f"{timeout_seconds:g}s after its first prompt "
                f"(last status: {last_status!r})"
            )
        sleep(min(poll_interval_seconds, remaining))

def start_agent_when_pane_ready(
    start_args: list[str],
    *,
    timeout_seconds: float = AGENT_START_PANE_READY_TIMEOUT_SECONDS,
    poll_interval_seconds: float = AGENT_START_PANE_READY_POLL_INTERVAL_SECONDS,
) -> None:
    deadline = monotonic() + timeout_seconds
    while True:
        try:
            run_herdr(start_args)
            return
        except ValueError as exc:
            remaining = deadline - monotonic()
            if (
                not isinstance(exc, HerdrCommandError)
                or exc.error_code != "agent_pane_busy"
                or remaining <= 0
            ):
                raise
            sleep(min(poll_interval_seconds, remaining))

def settle_window_seconds() -> float:
    override = os.environ.get("STRAW_BOSS_AGENT_SETTLE_SECONDS")
    return float(override) if override else AGENT_SETTLE_WINDOW_SECONDS

def settled_agent(pane_id: str) -> dict[str, object]:
    """Read the agent, holding the reading open long enough to catch a gate.

    A single read straight after `agent start` catches a Claude worker still
    reporting idle while its folder-trust gate is up; the task then goes to the
    gate instead of a turn, and the gate's own preselected option exits the
    worker. Returns as soon as a blocked state appears, so a healthy launch
    pays this window only once.
    """
    deadline = monotonic() + settle_window_seconds()
    agent = live_agent(pane_id)
    while agent.get("agent_status") != "blocked":
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        sleep(min(AGENT_SETTLE_POLL_INTERVAL_SECONDS, remaining))
        agent = live_agent(pane_id)
    return agent

def startup_gate(pane_id: str, agent: dict[str, object]) -> tuple[str, bool] | None:
    """The pane's text when a Claude worker is stopped before its first turn.

    Two independent signals, because either alone has been observed to miss:
    herdr's own `blocked` classification, and the gate's preselected "No, exit"
    on the pane itself. The second flag says which fired -- only the pane
    marker identifies the gate specifically enough to name its options, so a
    blocked-only reading reports what it actually knows instead of prescribing
    keystrokes for a dialog it has not recognised.
    """
    excerpt = pane_excerpt(pane_id)
    marker_seen = normalize_transcript_text(
        STARTUP_GATE_PANE_MARKER
    ) in normalize_transcript_text(excerpt)
    if marker_seen or agent.get("agent_status") == "blocked":
        return excerpt, marker_seen
    return None
