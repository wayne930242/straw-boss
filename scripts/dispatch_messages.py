"""Message validation, envelopes, and delivery-ledger records for dispatches."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


WORKER_TO_MAIN_INTENTS = frozenset({"question", "inform", "status"})
MAIN_TO_WORKER_INTENTS = frozenset(
    {"inform", "redirect", "reply", "reply-retry", "control"}
)
PEER_INTENTS = frozenset({"question", "answer"})
SENTENCE_END_RE = re.compile(r"[.!?。！？]+(?=\s|$)")


class EndpointView(Protocol):
    target: str
    expected_session_id: str | None


def validate_delta_message(message: str) -> str:
    text = message.strip()
    if not text:
        raise ValueError("message must be non-empty")
    endings = list(SENTENCE_END_RE.finditer(text))
    sentence_count = len(endings)
    if not endings or text[endings[-1].end() :].strip():
        sentence_count += 1
    sentence_count = max(
        sentence_count,
        len([line for line in text.splitlines() if line.strip()]),
    )
    if sentence_count > 2:
        raise ValueError(
            "live message must be delta-only and at most two sentences; use --ref for detail"
        )
    return text


def normalize_references(
    references: list[str] | tuple[str, ...],
) -> tuple[str, ...]:
    normalized: list[str] = []
    for reference in references:
        value = reference.strip()
        if not value:
            raise ValueError("--ref must be non-empty")
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def dispatch_label(path: Path, instruction: dict[str, Any]) -> str:
    app = str(instruction.get("app", "unknown-app"))
    stem = path.name.removesuffix(".json")
    dispatch_id = instruction.get("task_id") or stem.removeprefix(f"{app}--")
    return f"{app}/{dispatch_id}"


def delivery_ledger_path(instruction_path: Path) -> Path:
    return instruction_path.with_name(
        f"{instruction_path.name.removesuffix('.json')}.messages.jsonl"
    )


def validate_peer_reply(
    sender_path: Path,
    source: EndpointView,
    endpoint: EndpointView,
    in_reply_to: str,
) -> None:
    try:
        records = [
            json.loads(line)
            for line in delivery_ledger_path(sender_path).read_text().splitlines()
        ]
    except (OSError, json.JSONDecodeError):
        records = []
    if not any(
        record.get("message_id") == in_reply_to
        and record.get("intent") == "question"
        and record.get("source_session_id") == endpoint.expected_session_id
        and record.get("target_session_id") == source.expected_session_id
        for record in records
        if isinstance(record, dict)
    ):
        raise ValueError(
            f"unknown peer question {in_reply_to!r} for this sender/receiver pair"
        )


def append_delivery_record(
    instruction_path: Path,
    source: EndpointView,
    endpoint: EndpointView,
    intent: str,
    message: str,
    message_id: str,
    in_reply_to: str | None,
    references: tuple[str, ...],
    undeliverable_reason: str | None = None,
) -> None:
    record = {
        "direction": f"to-{endpoint.target}",
        "intent": intent,
        "message_id": message_id,
        "in_reply_to": in_reply_to,
        "source_session_id": source.expected_session_id,
        "target_session_id": endpoint.expected_session_id,
        "message_sha256": hashlib.sha256(message.encode()).hexdigest(),
        "message_length": len(message),
        "reference_count": len(references),
        "reference_sha256": [
            hashlib.sha256(reference.encode()).hexdigest()
            for reference in references
        ],
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    if undeliverable_reason is not None:
        # A delivered record only needs hashes: the body already reached the
        # other side. An undelivered one is the opposite -- the body exists
        # nowhere else, so storing only its hash would discard the very thing
        # someone has to read to pick the conversation back up.
        record["delivered"] = False
        record["undeliverable_reason"] = undeliverable_reason
        record["message"] = message
        record["references"] = list(references)
    with delivery_ledger_path(instruction_path).open("a") as stream:
        stream.write(json.dumps(record) + "\n")


def format_message_envelope(
    *,
    path: Path,
    instruction: dict[str, Any],
    target: str,
    intent: str,
    message: str,
    delivery_id: str,
    references: tuple[str, ...],
    sender_path: Path | None,
    sender_instruction: dict[str, Any] | None,
    in_reply_to: str | None,
) -> str:
    reference_suffix = (
        f" refs={json.dumps(references, separators=(',', ':'))}" if references else ""
    )
    if intent == "control":
        return message
    if sender_instruction is not None:
        assert sender_path is not None
        sender = dispatch_label(sender_path, sender_instruction)
        if intent == "question":
            return (
                f"[peer question id={delivery_id} from={sender} "
                f"reply-to={sender_path}{reference_suffix}] {message}"
            )
        return (
            f"[peer answer id={delivery_id} in-reply-to={in_reply_to} "
            f"from={sender}{reference_suffix}] {message}"
        )
    if target in ("main", "root-main"):
        sender_role = "coworker" if target == "root-main" else "dispatched-agent"
        return (
            f"[{sender_role} {intent} from={dispatch_label(path, instruction)}"
            f"{reference_suffix}] {message}"
        )
    return f"[main-agent {intent}{reference_suffix}] {message}"
