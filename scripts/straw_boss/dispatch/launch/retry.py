"""Classifying a failed launch attempt and deciding whether to retry it."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from straw_boss.dispatch.state import (
    dump_json,
    launch_failure_path,
    load_json,
)
from straw_boss.herdr.transport import (
    HerdrCommandError,
    normalize_transcript_text,
)


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

# Whole-launch retries, so a transient trip does not become four hand-run
# relaunches by the coordinator. Deliberately short and bounded: the failures
# worth retrying are races, and everything else is reported instead.
LAUNCH_RETRY_BACKOFF_SECONDS = (0.0, 3.0, 8.0)

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

# Codex answers `agent prompt` with `agent_blocked` while its model list is
# still resolving, even though the pane already shows a ready composer. That is
# a boot race a second attempt clears, not a gate -- but `agent_blocked` alone
# cannot say which, and blanket-retrying it would burn panes on the gates that
# code also covers. Both markers together are what distinguishes them: a gate
# renders its own prompt in place of the composer, and a resolved model never
# reads `loading`. Matched whitespace-normalized, because the pane pads the
# model row and a narrow worker pane wraps it.
CODEX_READY_COMPOSER_MARKER = "Ask Codex to do anything"

CODEX_MODEL_LOADING_MARKER = "model: loading"

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

def codex_model_still_loading(error: ValueError, excerpt: str) -> bool:
    """A Codex worker herdr calls blocked only because its model is unresolved.

    Narrow on purpose: the error code alone also covers the startup gates that
    no retry can answer, so the ready composer must be on the pane too.
    """
    if (
        not isinstance(error, HerdrCommandError)
        or error.error_code != "agent_blocked"
    ):
        return False
    normalized = normalize_transcript_text(excerpt)
    return (
        normalize_transcript_text(CODEX_READY_COMPOSER_MARKER) in normalized
        and normalize_transcript_text(CODEX_MODEL_LOADING_MARKER) in normalized
    )

def is_retryable(error: ValueError, excerpt: str = "") -> bool:
    if (
        isinstance(error, HerdrCommandError)
        and error.error_code in RETRYABLE_HERDR_ERROR_CODES
    ):
        return True
    if SPENT_SESSION_PANE_MARKER in excerpt:
        return True
    return codex_model_still_loading(error, excerpt)

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
