#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Start and prompt a herdr dispatched agent with its mandatory contract."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from agent_naming import derive_agent_name, live_names, unique_agent_name
from dispatch_state import (
    dump_json,
    launch_failure_path,
    launch_receipt_path,
    load_json,
    sha256_text,
)
from dispatch_transport import (
    HerdrCommandError,
    confirm_transcript_contains,
    normalize_transcript_text,
    prompt_delivery_args,
    run_herdr,
    run_herdr_raw,
)


AGENT_START_PANE_READY_TIMEOUT_SECONDS = 5.0
AGENT_START_PANE_READY_POLL_INTERVAL_SECONDS = 0.25
# `agent start` returning only proves the process launched -- the agent's TUI is
# not necessarily able to turn input into a turn yet. On a loaded machine a fresh
# Claude session spends tens of seconds attaching MCP servers first, and a prompt
# sent inside that window lands in the composer: herdr reports
# agent_prompt_stalled, which reads like a delivery bug but is really "asked too
# early". Two back-to-back attempts give that window ~16s to close, which is not
# enough on a busy host, so back off between attempts instead.
#
# Gating on herdr's `interactive_ready` was considered and rejected: live agents
# were observed working with the field absent entirely, so absence cannot be read
# as "not ready" and the signal is not dependable as a gate.
PROMPT_RETRY_BACKOFF_SECONDS = (0.0, 2.0, 5.0, 10.0)
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
# Whole-launch retries, so a transient trip does not become four hand-run
# relaunches by the coordinator. Deliberately short and bounded: the failures
# worth retrying are races, and everything else is reported instead.
LAUNCH_RETRY_BACKOFF_SECONDS = (0.0, 3.0, 8.0)
PANE_EXCERPT_LINES = 60
PANE_EXCERPT_MAX_CHARS = 2000
# herdr codes that mean the target went away or was momentarily unavailable --
# the shapes a second attempt can actually clear. Everything else (a refused
# start, a mismatched identity, a pane in the wrong tab) is a standing
# condition of this cwd or configuration: retrying it only burns another pane
# and delays the pane excerpt that says why.
RETRYABLE_HERDR_ERROR_CODES = frozenset(
    {"agent_not_running", "agent_not_found", "pane_not_found", "agent_pane_busy"}
)
# `claude --session-id` refuses an id it has already seen and exits before herdr
# can report anything richer than a failed start, so this refusal only ever
# exists on the pane. A retry mints a fresh id, which is exactly what clears it.
SPENT_SESSION_PANE_MARKER = "is already in use"
TASK_DELIVERY_MARKER_PREFIX = "sb256"
MAX_NAME_COLLISION_ATTEMPTS = 5


def _option_present(args: list[str], flags: tuple[str, ...]) -> bool:
    return any(
        arg in flags or any(arg.startswith(f"{flag}=") for flag in flags)
        for arg in args
    )


def _codex_effort_present(args: list[str]) -> bool:
    return any(
        arg.startswith("model_reasoning_effort=")
        or arg.startswith("-c=model_reasoning_effort=")
        or arg.startswith("--config=model_reasoning_effort=")
        for arg in args
    )


def provider_profile_args(
    instruction: dict[str, object], extra_args: list[str]
) -> list[str]:
    agent_kind = str(instruction.get("agent_kind"))
    profile = instruction.get("agent_profile")
    model = instruction.get("agent_model")
    effort = instruction.get("agent_effort")
    advisor = instruction.get("advisor_model")

    for value, label in (
        (profile, "agent_profile"),
        (model, "agent_model"),
        (effort, "agent_effort"),
        (advisor, "advisor_model"),
    ):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"dispatch instruction has invalid {label}")

    resolved: list[str] = []
    if agent_kind == "claude":
        mappings = (
            (profile, ("--agent",)),
            (model, ("--model",)),
            (effort, ("--effort",)),
            (advisor, ("--advisor",)),
        )
        for value, flags in mappings:
            if value is None:
                continue
            if _option_present(extra_args, flags):
                raise ValueError(
                    f"raw provider argument {flags[0]} duplicates the dispatch instruction"
                )
            resolved.extend([flags[0], str(value)])
    elif agent_kind == "codex":
        if advisor is not None:
            raise ValueError("Codex has no native advisor; advisor_model requires Claude Code")
        for value, flags, emitted_flag in (
            (profile, ("--profile", "-p"), "--profile"),
            (model, ("--model", "-m"), "--model"),
        ):
            if value is None:
                continue
            if _option_present(extra_args, flags):
                raise ValueError(
                    f"raw provider argument {emitted_flag} duplicates the dispatch instruction"
                )
            resolved.extend([emitted_flag, str(value)])
        if effort is not None:
            if _codex_effort_present(extra_args):
                raise ValueError(
                    "raw model_reasoning_effort duplicates the dispatch instruction"
                )
            resolved.extend(["-c", f"model_reasoning_effort={effort}"])
    else:
        raise ValueError(f"unsupported agent kind {agent_kind!r}")

    return [*resolved, *extra_args]


def live_agent(pane_id: str) -> dict[str, object]:
    payload = run_herdr(["agent", "get", pane_id])
    agent = payload.get("result", {}).get("agent")
    if not isinstance(agent, dict):
        raise ValueError(f"herdr could not resolve the launched agent in pane {pane_id!r}")
    return agent


def live_agent_terminal_id(pane_id: str, agent_kind: str) -> str:
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
    return terminal_id


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


def wait_for_agent_session(
    pane_id: str,
    *,
    timeout_seconds: float = 15.0,
    poll_interval_seconds: float = 0.25,
) -> str:
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
            raise ValueError(
                "launched agent did not expose agent_session.value within "
                f"{timeout_seconds:g}s after its first prompt "
                f"(last status: {last_status!r})"
            )
        sleep(min(poll_interval_seconds, remaining))


def herdr_pane(pane_id: str) -> dict[str, object]:
    payload = run_herdr(["pane", "get", pane_id])
    pane = payload.get("result", {}).get("pane")
    if not isinstance(pane, dict) or pane.get("pane_id") != pane_id:
        raise ValueError(f"herdr could not resolve pane {pane_id!r}")
    if not pane.get("tab_id"):
        raise ValueError(f"herdr pane {pane_id!r} did not expose a tab id")
    return pane


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


def create_worker_pane(instruction: dict[str, object]) -> tuple[str, str]:
    main_pane_id = instruction.get("main_agent_herdr_pane_id")
    if not isinstance(main_pane_id, str) or not main_pane_id:
        raise ValueError("dispatch instruction has no main-agent herdr pane")
    main_pane = herdr_pane(main_pane_id)
    main_tab_id = str(main_pane["tab_id"])

    cwd = Path(str(instruction.get("repo_root", ""))).resolve()
    if not cwd.is_dir():
        raise ValueError(f"dispatch repo_root is not a directory: {cwd}")
    payload = run_herdr(
        [
            "pane",
            "split",
            main_pane_id,
            "--direction",
            "right",
            "--cwd",
            str(cwd),
            "--no-focus",
        ]
    )
    pane = payload.get("result", {}).get("pane")
    if not isinstance(pane, dict):
        raise ValueError("herdr pane split did not return a pane")
    pane_id = pane.get("pane_id")
    tab_id = pane.get("tab_id")
    if not isinstance(pane_id, str) or not pane_id:
        raise ValueError("herdr pane split did not return a pane id")
    if tab_id != main_tab_id:
        try:
            run_herdr(["pane", "close", pane_id])
        except ValueError as close_error:
            raise ValueError(
                f"worker pane landed in tab {tab_id!r}, expected {main_tab_id!r}; "
                f"cleanup also failed: {close_error}"
            ) from close_error
        raise ValueError(
            f"worker pane landed in tab {tab_id!r}, expected main-agent tab {main_tab_id!r}"
        )
    return pane_id, main_tab_id


def name_worker_pane(pane_id: str, name: str) -> str | None:
    """Best-effort pane label after the final agent name is known.

    A label improves operator orientation but is not part of dispatch identity,
    so two failed attempts return a warning instead of blocking task delivery.
    """
    last_error: ValueError | None = None
    for _ in range(2):
        try:
            run_herdr(["pane", "rename", pane_id, name])
            return None
        except ValueError as exc:
            last_error = exc
    assert last_error is not None
    return f"worker pane {pane_id!r} could not be named {name!r}: {last_error}"


def name_coordinator_tab(instruction: dict[str, object]) -> str | None:
    """Best-effort shared-tab label before the worker pane is created."""
    main_pane_id = instruction.get("main_agent_herdr_pane_id")
    if not isinstance(main_pane_id, str) or not main_pane_id:
        return "coordinator tab naming skipped: dispatch has no main-agent pane"
    label = derive_agent_name("coordinator", str(instruction["app"]))
    try:
        tab_id = str(herdr_pane(main_pane_id)["tab_id"])
    except ValueError as exc:
        return f"coordinator tab naming failed; dispatch continued: {exc}"
    last_error: ValueError | None = None
    for _ in range(2):
        try:
            run_herdr(["tab", "rename", tab_id, label])
            return None
        except ValueError as exc:
            last_error = exc
    assert last_error is not None
    return (
        f"coordinator tab {tab_id!r} could not be named {label!r}; "
        f"dispatch continued: {last_error}"
    )


class LaunchAttemptError(ValueError):
    """One failed launch attempt, classified for the retry decision above it.

    `retryable` separates "something transient tripped this attempt" from "this
    cwd or configuration cannot succeed as asked", where a fourth identical
    attempt only burns another pane. `keep_pane` marks the attempts whose pane
    still holds a live agent someone can act on -- closing that pane is how a
    recoverable situation turns into a lost worker. `pane_excerpt` carries what
    the pane was showing, because herdr's error code says the agent is gone and
    never says why.
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        pane_id: str | None = None,
        keep_pane: bool = False,
        pane_excerpt: str = "",
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.pane_id = pane_id
        self.keep_pane = keep_pane
        self.pane_excerpt = pane_excerpt


def is_retryable(error: ValueError, excerpt: str = "") -> bool:
    if (
        isinstance(error, HerdrCommandError)
        and error.error_code in RETRYABLE_HERDR_ERROR_CODES
    ):
        return True
    return SPENT_SESSION_PANE_MARKER in excerpt


def pane_excerpt(pane_id: str) -> str:
    """What the worker pane was showing when an attempt failed.

    The agent's own last words -- a startup gate, a refused session id, a crash
    -- exist only on that pane, and the failure path closes it, so read it
    before deciding anything.
    """
    try:
        text = run_herdr_raw(
            [
                "pane",
                "read",
                pane_id,
                "--lines",
                str(PANE_EXCERPT_LINES),
                "--source",
                "visible",
            ]
        )
    except ValueError:
        return ""
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)[-PANE_EXCERPT_MAX_CHARS:].strip()


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


def rotate_session_id(inst_path: Path, instruction: dict[str, Any]) -> str:
    """Give the next attempt an unused Claude session id.

    `claude --session-id` refuses an id it has already seen ("Session ID ... is
    already in use") and exits at once, so any relaunch reusing the id a
    previous attempt already handed to a booted agent is guaranteed to die at
    startup. The instruction is still `pending` here -- nothing has been
    confirmed against this id -- so it is updated in place and stays the single
    record of the endpoint the worker will answer on.
    """
    instruction["session_id"] = str(uuid.uuid4())
    dump_json(inst_path, instruction)
    return str(instruction["session_id"])


def spent_session_ids(inst_path: Path) -> set[str]:
    """Every session id any earlier run of this dispatch already started with.

    Accumulated across runs rather than derived from the current attempt list,
    because each run rewrites that list -- an id spent two runs ago is still
    spent.
    """
    path = launch_failure_path(inst_path)
    if not path.is_file():
        return set()
    try:
        record = load_json(path)
    except (OSError, json.JSONDecodeError):
        return set()
    spent = {
        str(value)
        for value in record.get("spent_session_ids", [])
        if isinstance(value, str) and value
    }
    attempts = record.get("attempts")
    if isinstance(attempts, list):
        spent.update(
            str(attempt.get("session_id"))
            for attempt in attempts
            if isinstance(attempt, dict) and attempt.get("session_id")
        )
    return spent


def record_launch_failure(
    inst_path: Path, attempts: list[dict[str, Any]], spent: set[str]
) -> Path:
    """Leave the reason beside the instruction, not only on the caller's stderr.

    A launch that never succeeds writes no receipt and leaves the instruction
    `pending`, so without this an abandoned dispatch looks exactly like one
    nobody ever started -- with no pane id to go and look at. Rewritten after
    every failed attempt, not only at the end, so a run killed mid-retry still
    leaves the trail this file exists to guarantee.
    """
    path = launch_failure_path(inst_path)
    dump_json(
        path,
        {
            "instruction_path": str(inst_path),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "spent_session_ids": sorted(spent),
            "attempts": attempts,
        },
    )
    return path


def launch_failure_message(
    error: LaunchAttemptError, attempts: list[dict[str, Any]], failure_path: Path
) -> str:
    lines = [f"launch failed after {len(attempts)} attempt(s): {error}"]
    if error.keep_pane and error.pane_id:
        lines.append(
            f"worker pane {error.pane_id!r} is left open with its agent running; act on it "
            "there rather than relaunching into a second pane"
        )
    if error.pane_excerpt:
        lines.append(f"pane {error.pane_id} was showing:\n{error.pane_excerpt}")
    lines.append(f"attempt trail recorded at {failure_path}")
    return "\n".join(lines)


class PromptDeliveryError(ValueError):
    """The agent started but its first prompt could not be confirmed as a turn.

    Kept distinct from other launch failures because the failure surface is
    different: the pane and the agent are both alive and healthy, only the
    handoff of the opening prompt did not land. Destroying that pane discards a
    booted agent and forces a full relaunch, so the caller leaves it standing
    and reports where it is.
    """

    def __init__(self, message: str, pane_id: str) -> None:
        super().__init__(message)
        self.pane_id = pane_id


def task_delivery_marker(task: str) -> str:
    digest = base64.urlsafe_b64encode(bytes.fromhex(sha256_text(task))).decode("ascii")
    return f"[{TASK_DELIVERY_MARKER_PREFIX}:{digest.rstrip('=')}]"


def task_start_prompt(task: str) -> str:
    return f"Begin contract task.\n{task_delivery_marker(task)}"


def _backoff_seconds(variable: str, default: tuple[float, ...]) -> tuple[float, ...]:
    """Delay before each attempt, overridable for tests.

    Tests drive a fake herdr that answers instantly, so real backoff would only
    buy wall-clock; production needs it because the thing being waited out is a
    booting agent.
    """
    override = os.environ.get(variable)
    if not override:
        return default
    return tuple(float(part) for part in override.split(",") if part.strip())


def prompt_retry_backoff_seconds() -> tuple[float, ...]:
    return _backoff_seconds(
        "STRAW_BOSS_PROMPT_RETRY_BACKOFF_SECONDS", PROMPT_RETRY_BACKOFF_SECONDS
    )


def launch_retry_backoff_seconds() -> tuple[float, ...]:
    return _backoff_seconds(
        "STRAW_BOSS_LAUNCH_RETRY_BACKOFF_SECONDS", LAUNCH_RETRY_BACKOFF_SECONDS
    )


def prompt_task_with_confirmation(pane_id: str, task: str, agent_kind: str) -> None:
    marker = task_delivery_marker(task)
    prompt = task_start_prompt(task)
    backoff = prompt_retry_backoff_seconds()
    attempts_remaining = len(backoff)
    while attempts_remaining:
        delay = backoff[len(backoff) - attempts_remaining]
        attempts_remaining -= 1
        if delay:
            sleep(delay)
        pre_send_status = live_agent(pane_id).get("agent_status")
        pre_send_status = pre_send_status if isinstance(pre_send_status, str) else None
        try:
            run_herdr(prompt_delivery_args(pane_id, prompt, pre_send_status))
        except HerdrCommandError as exc:
            if exc.error_code != "agent_prompt_stalled":
                raise
            if not attempts_remaining:
                raise PromptDeliveryError(
                    f"sent the initial task to pane {pane_id!r} via herdr "
                    f"{len(backoff)} times but herdr confirmed no attempt started a turn "
                    "(agent_prompt_stalled: the prompt likely reached only the composer, "
                    "not a real turn); refusing to write a launch receipt",
                    pane_id,
                ) from exc
            continue
        if confirm_transcript_contains(pane_id, marker, agent_kind):
            return
    raise PromptDeliveryError(
        f"sent the initial task to pane {pane_id!r} via herdr {len(backoff)} times but "
        "could not confirm it landed in the transcript via its delivery marker; refusing "
        "to write a launch receipt",
        pane_id,
    )


def launch(
    instruction_path: str,
    name: str | None,
    agent_args: list[str],
) -> dict[str, Any]:
    inst_path = Path(instruction_path).resolve()
    if not inst_path.is_file():
        raise ValueError(f"no instruction file at {inst_path}")
    instruction = load_json(inst_path)
    if instruction.get("status") != "pending":
        raise ValueError("only a pending dispatch can be launched")
    if instruction.get("mode") != "herdr-pane":
        raise ValueError("launch-dispatched-agent.py currently supports herdr-pane dispatches")

    contract_path = Path(str(instruction.get("contract_path", "")))
    if not contract_path.is_file():
        raise ValueError(f"dispatch contract is missing at {contract_path}")
    contract = contract_path.read_text()
    if sha256_text(contract) != instruction.get("contract_sha256"):
        raise ValueError("dispatch contract digest does not match the instruction")

    is_coworker = bool(instruction.get("parent_instruction_path"))
    name_is_derived = name is None
    base_candidate_name = ""
    known_taken_names: set[str] = set()
    if name_is_derived:
        agent_role = "coworker" if is_coworker else "worker"
        workroom = instruction.get("role") or instruction["app"]
        base_candidate_name = derive_agent_name(agent_role, str(workroom))
        known_taken_names = live_names(run_herdr(["agent", "list"]))
        name = unique_agent_name(base_candidate_name, known_taken_names)
        known_taken_names.add(name)

    agent_kind = str(instruction.get("agent_kind"))
    base_provider_args = provider_profile_args(instruction, agent_args)
    coordinator_tab_warning = (
        None if is_coworker else name_coordinator_tab(instruction)
    )

    def provider_args_for(current_name: str) -> list[str]:
        if agent_kind == "claude":
            return [
                "--session-id",
                str(instruction["session_id"]),
                "--name",
                current_name,
                "--append-system-prompt-file",
                str(contract_path),
                *base_provider_args,
            ]
        if agent_kind == "codex":
            return [
                "-c",
                (
                    "developer_instructions=Before any task action, read and follow "
                    f"the mandatory contract at {contract_path}."
                ),
                *base_provider_args,
            ]
        raise ValueError(f"unsupported agent kind {agent_kind!r}")

    def attempt() -> dict[str, Any]:
        nonlocal name
        # Set once the worker is confirmed to be holding the task: from there
        # on nothing in this launch may close its pane, for the same reason a
        # missed prompt handoff does not -- the agent is booted and working,
        # and only this launcher's own bookkeeping is unfinished.
        delivered = False
        provider_args = provider_args_for(str(name))
        pane_label_warning: str | None = None
        try:
            pane_id, tab_id = create_worker_pane(instruction)
        except ValueError as exc:
            # No pane survived this, including the tab-mismatch case that closes
            # its own; there is nothing to keep and nothing to read.
            raise LaunchAttemptError(str(exc), retryable=is_retryable(exc)) from exc
        try:
            start_error: ValueError | None = None
            collision_retries = 0
            while True:
                try:
                    start_agent_when_pane_ready(
                        [
                            "agent",
                            "start",
                            str(name),
                            "--kind",
                            agent_kind,
                            "--pane",
                            pane_id,
                            "--",
                            *provider_args,
                        ]
                    )
                    break
                except HerdrCommandError as exc:
                    if (
                        not name_is_derived
                        or exc.error_code != "agent_name_taken"
                        or collision_retries >= MAX_NAME_COLLISION_ATTEMPTS
                    ):
                        start_error = exc
                        break
                    collision_retries += 1
                    name = unique_agent_name(base_candidate_name, known_taken_names)
                    known_taken_names.add(name)
                    provider_args = provider_args_for(str(name))
                except ValueError as exc:
                    start_error = exc
                    break

            try:
                agent = settled_agent(pane_id)
            except ValueError:
                if start_error is not None:
                    raise start_error
                raise
            if start_error is not None and agent.get("agent_status") != "blocked":
                raise start_error
            pane_label_warning = name_worker_pane(pane_id, str(name))
            gate = startup_gate(pane_id, agent) if agent_kind == "claude" else None
            if gate is not None or agent.get("agent_status") == "blocked":
                if agent_kind == "claude":
                    # Claude Code's startup gates -- folder trust first among
                    # them -- render as a select list whose highlighted option
                    # is "No, exit". Enter, or the task itself which ends in
                    # one, picks that option and exits a worker that had
                    # already booted. No retry can answer this; a human can, in
                    # this pane, and answering it also records the decision so
                    # the next launch into this directory runs clean.
                    gate_excerpt, marker_seen = gate if gate else ("", False)
                    recovery = (
                        'the gate preselects "No, exit" and anything sent there would '
                        "exit the worker. Answer it in the Herdr tab (or "
                        f"`herdr agent send-keys {pane_id} down enter` to take the "
                        "second option), then close that pane and run this launch again"
                        if marker_seen
                        else "only a human can answer what it is waiting on, and a "
                        "blind keystroke risks picking a decline option that exits "
                        "the worker. Answer it in the Herdr tab from what the pane "
                        "shows below, then close that pane and run this launch again"
                    )
                    raise LaunchAttemptError(
                        f"the worker in pane {pane_id!r} stopped on a Claude Code "
                        "startup gate before its first turn, so the task cannot be "
                        f"submitted: {recovery}",
                        retryable=False,
                        pane_id=pane_id,
                        keep_pane=True,
                        pane_excerpt=gate_excerpt or pane_excerpt(pane_id),
                    )
                run_herdr(["agent", "send-keys", pane_id, "enter"])
                run_herdr(
                    [
                        "agent",
                        "wait",
                        pane_id,
                        "--until",
                        "idle",
                        "--until",
                        "blocked",
                        "--timeout",
                        "15000",
                    ]
                )

            prompt_task_with_confirmation(
                pane_id, str(instruction["task"]), agent_kind
            )
            delivered = True
            terminal_id = live_agent_terminal_id(pane_id, agent_kind)
            session_id: str | None = None
            if agent_kind == "claude":
                session_id = wait_for_agent_session(pane_id)
                if session_id != instruction.get("session_id"):
                    raise ValueError(
                        f"launched Claude session {session_id!r} does not match preassigned session "
                        f"{instruction.get('session_id')!r}"
                    )
        except LaunchAttemptError:
            raise
        except PromptDeliveryError as exc:
            # The agent is up; only the opening prompt did not land. Closing the
            # pane here would throw away a booted session whose sole defect is a
            # missed handoff, so leave it standing and say where it is.
            raise LaunchAttemptError(
                str(exc),
                retryable=False,
                pane_id=exc.pane_id,
                keep_pane=True,
                pane_excerpt=pane_excerpt(exc.pane_id),
            ) from exc
        except ValueError as exc:
            excerpt = pane_excerpt(pane_id)
            if delivered:
                raise LaunchAttemptError(
                    f"{exc}; the task was already confirmed delivered, so the worker in "
                    f"pane {pane_id!r} is running it and only this launch's own "
                    "bookkeeping failed -- no receipt is written, so the instruction "
                    "stays pending until someone reconciles it",
                    retryable=False,
                    pane_id=pane_id,
                    keep_pane=True,
                    pane_excerpt=excerpt,
                ) from exc
            raise LaunchAttemptError(
                str(exc),
                retryable=is_retryable(exc, excerpt),
                pane_id=pane_id,
                pane_excerpt=excerpt,
            ) from exc

        return {
            "name": str(name),
            "pane_id": pane_id,
            "tab_id": tab_id,
            "session_id": session_id,
            "herdr_terminal_id": terminal_id,
            "pane_label_warning": pane_label_warning,
        }

    spent = spent_session_ids(inst_path)
    if agent_kind == "claude" and str(instruction["session_id"]) in spent:
        # An earlier run of this launcher already handed that id to a started
        # agent, so reusing it now would only reproduce its startup refusal.
        rotate_session_id(inst_path, instruction)

    backoff = launch_retry_backoff_seconds()
    attempts: list[dict[str, Any]] = []
    landed: dict[str, Any] | None = None
    failure_path: Path | None = None
    for index, delay in enumerate(backoff):
        if delay:
            sleep(delay)
        if index and agent_kind == "claude" and attempts[-1]["pane_id"]:
            # Only an attempt that got as far as a pane can have started an
            # agent on the current id; one that never did leaves it unspent.
            rotate_session_id(inst_path, instruction)
        session_id_used = instruction.get("session_id")
        if session_id_used:
            spent.add(str(session_id_used))
        try:
            landed = attempt()
        except LaunchAttemptError as exc:
            record: dict[str, Any] = {
                "attempt": index + 1,
                "pane_id": exc.pane_id,
                "session_id": session_id_used,
                "retryable": exc.retryable,
                "pane_left_open": exc.keep_pane,
                "error": str(exc),
                "pane_excerpt": exc.pane_excerpt or None,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }
            if exc.pane_id and not exc.keep_pane:
                try:
                    run_herdr(["pane", "close", exc.pane_id])
                except ValueError as close_error:
                    record["pane_close_error"] = str(close_error)
            attempts.append(record)
            failure_path = record_launch_failure(inst_path, attempts, spent)
            if exc.retryable and index < len(backoff) - 1:
                continue
            raise ValueError(launch_failure_message(exc, attempts, failure_path)) from exc
        break

    assert landed is not None
    receipt = {
        "instruction_path": str(inst_path),
        "contract_sha256": instruction["contract_sha256"],
        "agent_kind": agent_kind,
        **landed,
        "launched_at": datetime.now(timezone.utc).isoformat(),
    }
    if coordinator_tab_warning is not None:
        receipt["coordinator_tab_label_warning"] = coordinator_tab_warning
    receipt_path = launch_receipt_path(inst_path)
    dump_json(receipt_path, receipt)
    launch_failure_path(inst_path).unlink(missing_ok=True)

    if not is_coworker:
        try:
            ensure_coordinator_named(instruction, live_names(run_herdr(["agent", "list"])))
        except ValueError:
            pass

    result: dict[str, Any] = {"launch_receipt_path": str(receipt_path), "launched": True}
    warnings = [
        warning
        for warning in (coordinator_tab_warning, landed.get("pane_label_warning"))
        if isinstance(warning, str) and warning
    ]
    if warnings:
        result["warning"] = "; ".join(warnings)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruction-path", required=True)
    parser.add_argument(
        "--name",
        default=None,
        help="operator-visible herdr agent name; omit for one derived automatically "
        "from the instruction's app and role",
    )
    parser.add_argument(
        "--agent-arg",
        action="append",
        default=[],
        help="additional provider argument; repeat once per argument",
    )
    args = parser.parse_args()
    try:
        result = launch(args.instruction_path, args.name, args.agent_arg)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
