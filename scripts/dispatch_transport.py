"""Session-validating herdr transport for every dispatch direction."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from time import sleep
from typing import Any

from dispatch_state import load_json
from dispatch_session import (
    Endpoint,
    HerdrCommandError,
    Target,
    resolve_endpoint,
    run_herdr,
    run_herdr_raw,
    validate_current_sender,
    validate_live_session,
    validate_status_sender,
    worker_endpoint_confirmed_closed,
)
from dispatch_messages import (
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
    if agent_kind not in {"claude", "codex"}:
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


class EndpointUnavailableError(ValueError):
    """The recipient's live session is gone, so the message cannot be handed over.

    Distinct from a malformed send because there is nothing the sender can fix:
    the other agent no longer exists. The message body is written to the
    delivery ledger before this is raised so the sender is not left holding an
    unrecorded question with no channel to ask it on.
    """


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
) -> Endpoint:
    path = Path(instruction_path).resolve()
    if not path.is_file():
        raise ValueError(f"no instruction file at {path}")
    instruction = load_json(path)
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
    run_herdr(prompt_delivery_args(endpoint.pane_id, envelope, pre_send_status))
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
    return endpoint
