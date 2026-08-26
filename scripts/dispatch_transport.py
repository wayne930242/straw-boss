"""Session-validating herdr transport for every dispatch direction."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from dispatch_state import load_json


SUBPROCESS_TIMEOUT_S = 30
Target = Literal["main", "worker"]
WORKER_TO_MAIN_INTENTS = frozenset({"question", "inform", "status"})
MAIN_TO_WORKER_INTENTS = frozenset({"inform", "redirect", "reply", "reply-retry", "control"})
PEER_INTENTS = frozenset({"question", "answer"})


@dataclass(frozen=True)
class Endpoint:
    target: Target
    pane_id: str
    expected_session_id: str
    agent_kind: str


def run_herdr_raw(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["herdr", *args],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"herdr {' '.join(args)!r} timed out") from exc
    except FileNotFoundError as exc:
        raise ValueError("herdr CLI not found on PATH") from exc
    if result.returncode != 0:
        raise ValueError(
            f"herdr {' '.join(args)!r} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def run_herdr(args: list[str]) -> dict[str, Any]:
    stdout = run_herdr_raw(args)
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"herdr {' '.join(args)!r} returned non-JSON output") from exc


def resolve_endpoint(instruction: dict[str, Any], target: Target) -> Endpoint:
    if target == "main":
        pane_id = instruction.get("main_agent_herdr_pane_id")
        session_id = instruction.get("main_agent_session_id")
        agent_kind = instruction.get("main_agent_kind")
    else:
        pane_id = instruction.get("herdr_pane_id")
        session_id = instruction.get("session_id")
        agent_kind = instruction.get("agent_kind")
    if not pane_id:
        raise ValueError(f"dispatch instruction has no {target} herdr pane")
    if not session_id:
        raise ValueError(f"dispatch instruction has no {target} session fingerprint")
    return Endpoint(target, str(pane_id), str(session_id), str(agent_kind or "unknown"))


def _is_foreground_claude_process(
    process: object, foreground_process_group_id: int
) -> bool:
    if not isinstance(process, dict) or process.get("pid") != foreground_process_group_id:
        return False
    executables = [process.get("argv0")]
    argv = process.get("argv")
    if isinstance(argv, list) and argv:
        executables.append(argv[0])
    return any(
        isinstance(executable, str) and Path(executable).name == "claude"
        for executable in executables
    )


def _claude_registry_corroborates(endpoint: Endpoint) -> bool:
    try:
        payload = run_herdr(["pane", "process-info", "--pane", endpoint.pane_id])
    except ValueError:
        return False

    process_info = payload.get("result", {}).get("process_info")
    if not isinstance(process_info, dict) or process_info.get("pane_id") != endpoint.pane_id:
        return False
    foreground_process_group_id = process_info.get("foreground_process_group_id")
    foreground_processes = process_info.get("foreground_processes")
    if (
        not isinstance(foreground_process_group_id, int)
        or isinstance(foreground_process_group_id, bool)
        or not isinstance(foreground_processes, list)
    ):
        return False
    candidates = [
        process
        for process in foreground_processes
        if _is_foreground_claude_process(process, foreground_process_group_id)
    ]
    if len(candidates) != 1:
        return False

    config_dir_value = os.environ.get("CLAUDE_CONFIG_DIR")
    config_dir = (
        Path(config_dir_value).expanduser()
        if config_dir_value
        else Path.home() / ".claude"
    )
    registry_path = config_dir / "sessions" / f"{foreground_process_group_id}.json"
    try:
        registry = load_json(registry_path)
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(registry, dict)
        and registry.get("pid") == foreground_process_group_id
        and registry.get("sessionId") == endpoint.expected_session_id
        and registry.get("kind") == "interactive"
        and registry.get("entrypoint") == "cli"
    )


def validate_live_session(endpoint: Endpoint) -> None:
    payload = run_herdr(["agent", "get", endpoint.pane_id])
    live_session_id = (
        payload.get("result", {}).get("agent", {}).get("agent_session", {}).get("value")
    )
    if live_session_id == endpoint.expected_session_id:
        return
    if endpoint.agent_kind == "claude" and _claude_registry_corroborates(endpoint):
        return
    raise ValueError(
        f"{endpoint.target} session mismatch for pane {endpoint.pane_id!r}: "
        f"expected {endpoint.expected_session_id!r}, live {live_session_id!r}; refusing to send"
    )


def validate_current_sender(endpoint: Endpoint) -> None:
    current_pane = os.environ.get("HERDR_PANE_ID")
    if current_pane != endpoint.pane_id:
        raise ValueError(
            f"sender pane mismatch: expected {endpoint.pane_id!r}, "
            f"current {current_pane!r}; refusing to send"
        )
    validate_live_session(endpoint)


def validate_status_sender(instruction_path: str | Path, status: str) -> None:
    path = Path(instruction_path).resolve()
    if not path.is_file():
        raise ValueError(f"no instruction file at {path}")
    instruction = load_json(path)
    if instruction.get("mode") != "herdr-pane":
        return
    source = resolve_endpoint(instruction, "main" if status == "cancelled" else "worker")
    validate_current_sender(source)


def _dispatch_label(path: Path, instruction: dict[str, Any]) -> str:
    app = str(instruction.get("app", "unknown-app"))
    stem = path.name.removesuffix(".json")
    dispatch_id = instruction.get("task_id") or stem.removeprefix(f"{app}--")
    return f"{app}/{dispatch_id}"


def _delivery_ledger_path(instruction_path: Path) -> Path:
    return instruction_path.with_name(
        f"{instruction_path.name.removesuffix('.json')}.messages.jsonl"
    )


def validate_peer_reply(
    sender_path: Path,
    source: Endpoint,
    endpoint: Endpoint,
    in_reply_to: str,
) -> None:
    ledger_path = _delivery_ledger_path(sender_path)
    try:
        records = [json.loads(line) for line in ledger_path.read_text().splitlines()]
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
        raise ValueError(f"unknown peer question {in_reply_to!r} for this sender/receiver pair")


def append_delivery_record(
    instruction_path: Path,
    source: Endpoint,
    endpoint: Endpoint,
    intent: str,
    message: str,
    message_id: str,
    in_reply_to: str | None,
) -> None:
    path = _delivery_ledger_path(instruction_path)
    record = {
        "direction": f"to-{endpoint.target}",
        "intent": intent,
        "message_id": message_id,
        "in_reply_to": in_reply_to,
        "source_session_id": source.expected_session_id,
        "target_session_id": endpoint.expected_session_id,
        "message_sha256": hashlib.sha256(message.encode()).hexdigest(),
        "message_length": len(message),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a") as stream:
        stream.write(json.dumps(record) + "\n")


def send_instruction_message(
    instruction_path: str | Path,
    target: Target,
    intent: str,
    message: str,
    *,
    sender_instruction_path: str | Path | None = None,
    in_reply_to: str | None = None,
    message_id: str | None = None,
) -> Endpoint:
    path = Path(instruction_path).resolve()
    if not path.is_file():
        raise ValueError(f"no instruction file at {path}")
    instruction = load_json(path)

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
    elif target == "main":
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
    validate_live_session(endpoint)
    delivery_id = message_id or str(uuid.uuid4())
    if intent == "control":
        if target != "worker" or not message.startswith("/"):
            raise ValueError("control intent requires a worker target and a slash command")
        envelope = message
    elif sender_instruction is not None:
        assert sender_path is not None
        sender_label = _dispatch_label(sender_path, sender_instruction)
        if intent == "question":
            envelope = (
                f"[peer question id={delivery_id} from={sender_label} "
                f"reply-to={sender_path}] {message}"
            )
        else:
            envelope = (
                f"[peer answer id={delivery_id} in-reply-to={in_reply_to} "
                f"from={sender_label}] {message}"
            )
    elif target == "main":
        envelope = f"[dispatched-agent {intent}] {message}"
    else:
        envelope = f"[main-agent {intent}] {message}"
    run_herdr(["agent", "prompt", endpoint.pane_id, envelope])
    append_delivery_record(
        path, source, endpoint, intent, message, delivery_id, in_reply_to
    )
    return endpoint
