"""Session-validating herdr transport for every dispatch direction."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from time import sleep
from typing import Any

from straw_boss.dispatch.state import load_json, resolve_instruction_status_path
from straw_boss.herdr.session import (
    Endpoint,
    HerdrCommandError,
    Target,
    resolve_coordinator_endpoint,
    resolve_endpoint,
    run_herdr,
    run_herdr_raw,
    validate_current_sender,
    validate_live_session,
    validate_status_sender,
    worker_endpoint_confirmed_closed,
)
from straw_boss.dispatch.messages import (
    MAIN_TO_WORKER_INTENTS,
    PEER_INTENTS,
    WORKER_TO_MAIN_INTENTS,
    append_delivery_record,
    format_message_envelope,
    normalize_references,
    validate_delta_message,
    validate_peer_reply,
)


# A generous tail prevents fast worker output from scrolling a delivered message
# away before the next poll and causing a duplicate resend.
TRANSCRIPT_CONFIRM_READ_LINES = 500
TRANSCRIPT_CONFIRM_POLL_ATTEMPTS = 6
TRANSCRIPT_CONFIRM_POLL_INTERVAL_S = 2.0
# herdr's own gate: from a non-working state, --wait requires an observed
# agent_status change within 5000ms or returns agent_prompt_stalled; a
# shorter --timeout turns that confirmed non-delivery into an ambiguous
# timeout instead, so this must stay >= 5000 (see `herdr agent prompt --help`).
PROMPT_LIFECYCLE_WAIT_TIMEOUT_MS = 8000
# States from which herdr's --wait gate above actually proves a new turn
# started: idle, done, and blocked are all "non-working" so the observed-
# change gate applies to them. Only an already-working target falls outside
# it -- herdr documents that --wait "does not track turns" once working, so
# that one state falls back to a plain submission instead of a false
# guarantee.
LIFECYCLE_CONFIRMABLE_STATUSES = frozenset({"idle", "done", "blocked"})


def read_agent_transcript(target: str, agent_kind: str) -> str:
    if agent_kind not in {"claude", "codex", "agy", "antigravity"}:
        raise ValueError(f"unsupported agent kind {agent_kind!r}")
    args = [
        "agent",
        "read",
        target,
        "--lines",
        str(TRANSCRIPT_CONFIRM_READ_LINES),
    ]
    if agent_kind == "codex":
        # Herdr's default recent source can be empty for a live Codex TUI even
        # while the visible screen contains the submitted prompt.
        return run_herdr_raw([*args, "--source", "visible"])
    try:
        return run_herdr_raw(args)
    except ValueError as exc:
        # A working Claude alternate screen can refuse scrollback capture while
        # its visible screen remains readable. Follow Herdr's own fallback hint.
        if "--source visible" not in str(exc):
            raise
        return run_herdr_raw([*args, "--source", "visible"])


def normalize_transcript_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def transcript_contains(transcript: str, message: str) -> bool:
    # Terminal rendering can replace spaces with newlines or insert whitespace
    # inside CJK text. Presence proves delivery; action is a separate concern.
    return normalize_transcript_text(message) in normalize_transcript_text(transcript)


def confirm_transcript_contains(
    target: str,
    message: str,
    agent_kind: str,
    *,
    attempts: int = TRANSCRIPT_CONFIRM_POLL_ATTEMPTS,
    poll_interval_seconds: float = TRANSCRIPT_CONFIRM_POLL_INTERVAL_S,
) -> bool:
    if attempts < 1:
        raise ValueError("transcript confirmation attempts must be positive")
    for attempt in range(attempts):
        if transcript_contains(read_agent_transcript(target, agent_kind), message):
            return True
        if attempt < attempts - 1:
            sleep(poll_interval_seconds)
    return False


def confirm_prompt_delivery(
    payload: dict[str, Any],
    pane_id: str,
    message: str,
    agent_kind: str,
    pre_send_status: str | None,
) -> None:
    """Accept a target-bound submission receipt or observed transcript text.

    Herdr's agent_prompted receipt follows writing both text and Enter. A busy
    pane queues that submission; idle/done/blocked submissions additionally
    passed prompt_delivery_args' lifecycle gate. Unknown states still require
    transcript evidence. A missing receipt or a truncated viewport is not
    evidence of non-delivery, so callers leave the submission alone.
    """
    result = payload.get("result")
    agent = result.get("agent") if isinstance(result, dict) else None
    expected_kind = "agy" if agent_kind == "antigravity" else agent_kind
    if (
        isinstance(result, dict)
        and result.get("type") == "agent_prompted"
        and isinstance(agent, dict)
        and agent.get("pane_id") == pane_id
        and agent.get("agent") == expected_kind
        and pre_send_status in LIFECYCLE_CONFIRMABLE_STATUSES | {"working"}
    ):
        return
    if confirm_transcript_contains(pane_id, message, agent_kind):
        return
    raise ValueError(
        f"herdr submission to pane {pane_id!r} returned successfully, but its "
        f"receipt did not confirm acceptance (pre-send status={pre_send_status!r}, "
        f"result type={result.get('type') if isinstance(result, dict) else None!r}, "
        f"receipt pane={agent.get('pane_id') if isinstance(agent, dict) else None!r}, "
        f"receipt provider={agent.get('agent') if isinstance(agent, dict) else None!r}); "
        f"the confirmation text was absent from {TRANSCRIPT_CONFIRM_POLL_ATTEMPTS} "
        "transcript reads; delivery remains unconfirmed and the message was not resent"
    )


def prompt_delivery_args(pane_id: str, text: str, pre_send_status: str | None) -> list[str]:
    """Build the `agent prompt` argv, using herdr's own lifecycle gate for
    confirmation when the pre-send state makes that gate meaningful.

    From `pre_send_status` idle/done/blocked, --wait makes a clean herdr exit
    mean a turn genuinely started; herdr itself raises agent_prompt_stalled
    if no state change is observed within 5000ms -- exactly the case where a
    prompt reached the composer but never started a turn. The --until target
    set depends on the starting state: from idle/done, either working or
    blocked is proof a turn began; from blocked, only working counts --
    re-observing blocked (a fresh permission prompt, or the same one) is not
    proof this specific prompt did anything, so accepting it back as a match
    would let the gate rubber-stamp a persistently-blocked pane. From any
    other status (already working, or missing/unrecognized), this stays a
    plain submission -- confirmation is then whatever the caller already
    does (transcript check, or nothing, unchanged from before this existed).
    """
    if pre_send_status not in LIFECYCLE_CONFIRMABLE_STATUSES:
        return ["agent", "prompt", pane_id, text]
    until_states = ["working"] if pre_send_status == "blocked" else ["working", "blocked"]
    args = ["agent", "prompt", pane_id, text, "--wait"]
    for state in until_states:
        args.extend(["--until", state])
    args.extend(["--timeout", str(PROMPT_LIFECYCLE_WAIT_TIMEOUT_MS)])
    return args


# herdr codes that mean "the target simply is not there any more", as opposed to
# "the target is there but is not who this dispatch expects".
ENDPOINT_MISSING_ERROR_CODES = frozenset({"agent_not_found", "pane_not_found"})
# herdr codes that reject a prompt before any input reaches the pane. Stalls and
# timeouts are excluded: their input was sent and may still sit in the composer.
PROMPT_REFUSED_ERROR_CODES = frozenset({"agent_blocked"})


class EndpointUnavailableError(ValueError):
    """The recipient's live session is gone, so the message cannot be handed over.

    Distinct from a malformed send because there is nothing the sender can fix:
    the other agent no longer exists. The message body is written to the
    delivery ledger before this is raised so the sender is not left holding an
    unrecorded question with no channel to ask it on.
    """


def validate_checkpoint_channel(
    path: Path, instruction: dict[str, Any], target: Target, intent: str,
) -> None:
    """Keep user-owned checkpoints on the user-facing conversation channel."""
    if target != "worker" and (target != "main" or intent != "question"):
        return
    status_path = resolve_instruction_status_path(path, instruction)
    try:
        status = load_json(status_path)
    except FileNotFoundError:
        return
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read dispatch status at {status_path}: {exc}") from exc
    if not isinstance(status, dict):
        raise ValueError(f"cannot read dispatch status at {status_path}: expected an object")
    if status.get("status") in {"awaiting-user-input", "awaiting-authorization"}:
        if target == "main":
            raise ValueError(
                f"dispatch status is {status['status']!r}; before asking the main agent, "
                "run report-task-status.py with --status awaiting-main-agent and an "
                "actionable note, then send the question so its reply can resolve "
                "the correct checkpoint"
            )
        raise ValueError(
            f"worker delivery refused: dispatch status is {status['status']!r}; "
            "present the information and references directly to the user in your "
            "user-facing conversation, and retain the dispatch until its next status event"
        )


def send_instruction_message(
    instruction_path: str | Path,
    target: Target,
    intent: str,
    message: str,
    *,
    sender_instruction_path: str | Path | None = None,
    in_reply_to: str | None = None,
    message_id: str | None = None,
    references: list[str] | tuple[str, ...] = (),
    confirm_delivery: bool = False,
) -> Endpoint:
    path = Path(instruction_path).resolve()
    if not path.is_file():
        raise ValueError(f"no instruction file at {path}")
    instruction = load_json(path)
    validate_checkpoint_channel(path, instruction, target, intent)
    normalized_references = normalize_references(references)
    if intent == "control":
        if normalized_references:
            raise ValueError("control intent does not accept --ref")
    else:
        message = validate_delta_message(message)

    sender_path: Path | None = None
    sender_instruction: dict[str, Any] | None = None
    if sender_instruction_path is not None:
        sender_path = Path(sender_instruction_path).resolve()
        if not sender_path.is_file():
            raise ValueError(f"no sender instruction file at {sender_path}")
        if sender_path == path:
            raise ValueError("peer sender and receiver instructions must differ")
        sender_instruction = load_json(sender_path)

    if sender_instruction is not None:
        if target != "worker" or intent not in PEER_INTENTS:
            raise ValueError(
                f"peer intent must be question or answer to worker, got {intent!r} to {target}"
            )
        if intent == "answer" and not in_reply_to:
            raise ValueError("peer answer requires --in-reply-to")
        if intent == "question" and in_reply_to:
            raise ValueError("peer question cannot set --in-reply-to")
        source = resolve_endpoint(sender_instruction, "worker")
    elif target in ("main", "root-main"):
        if target == "root-main" and (
            not instruction.get("parent_instruction_path") or intent != "status"
        ):
            raise ValueError("root-main accepts coworker status only")
        if intent not in WORKER_TO_MAIN_INTENTS:
            raise ValueError(f"worker-to-main intent {intent!r} is not allowed")
        source = resolve_endpoint(instruction, "worker")
    else:
        if intent in PEER_INTENTS:
            raise ValueError(f"peer intent {intent!r} requires --sender-instruction-path")
        if intent not in MAIN_TO_WORKER_INTENTS:
            raise ValueError(f"main-to-worker intent {intent!r} is not allowed")
        source = resolve_endpoint(instruction, "main")

    validate_current_sender(source)
    endpoint = resolve_endpoint(instruction, target)
    if sender_instruction is not None and intent == "answer":
        assert sender_path is not None and in_reply_to is not None
        validate_peer_reply(sender_path, source, endpoint, in_reply_to)
    delivery_id = message_id or str(uuid.uuid4())
    try:
        pre_send_status = validate_live_session(endpoint)
    except HerdrCommandError as exc:
        if exc.error_code not in ENDPOINT_MISSING_ERROR_CODES:
            # Identity mismatches (a different provider, a replaced terminal, a
            # reused coordinator pane) are refusals on purpose: the pane is live
            # but belongs to someone else, and handing the message over would
            # deliver it to the wrong agent. Only a genuinely absent target is
            # eligible for the recorded-undelivered path below.
            raise
        append_delivery_record(
            path,
            source,
            endpoint,
            intent,
            message,
            delivery_id,
            in_reply_to,
            normalized_references,
            undeliverable_reason=str(exc),
        )
        raise EndpointUnavailableError(
            f"{endpoint.target} session is no longer live ({exc}); the message is "
            f"recorded undelivered in the delivery ledger as {delivery_id}"
        ) from exc
    if intent == "control":
        if target != "worker" or not message.startswith("/"):
            raise ValueError("control intent requires a worker target and a slash command")
    envelope = format_message_envelope(
        path=path,
        instruction=instruction,
        target=target,
        intent=intent,
        message=message,
        delivery_id=delivery_id,
        references=normalized_references,
        sender_path=sender_path,
        sender_instruction=sender_instruction,
        in_reply_to=in_reply_to,
    )
    try:
        receipt = run_herdr(prompt_delivery_args(endpoint.pane_id, envelope, pre_send_status))
    except HerdrCommandError as exc:
        if exc.error_code not in PROMPT_REFUSED_ERROR_CODES:
            raise
        # The session validated live a moment ago, so this is the pane refusing
        # the hand-off rather than a missing target -- `agent_blocked` while it
        # waits on its own prompt. herdr sends no input on that refusal, so the
        # message is recoverable and worth resending, and the body has to
        # survive: without this the message is lost outright, a worse outcome
        # than the unreachable path above, which at least records it.
        append_delivery_record(
            path,
            source,
            endpoint,
            intent,
            message,
            delivery_id,
            in_reply_to,
            normalized_references,
            undeliverable_reason=str(exc),
        )
        raise EndpointUnavailableError(
            f"{endpoint.target} did not accept the hand-off ({exc}); the message is "
            f"recorded undelivered in the delivery ledger as {delivery_id} and can be "
            f"resent once that pane is free"
        ) from exc
    append_delivery_record(
        path,
        source,
        endpoint,
        intent,
        message,
        delivery_id,
        in_reply_to,
        normalized_references,
    )
    if confirm_delivery:
        confirm_prompt_delivery(
            receipt, endpoint.pane_id, message, endpoint.agent_kind, pre_send_status
        )
    return endpoint
