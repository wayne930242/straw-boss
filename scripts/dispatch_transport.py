"""Session-validating herdr transport for every dispatch direction."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import Any, Literal

from dispatch_state import load_json


SUBPROCESS_TIMEOUT_S = 30
# A generous tail prevents fast worker output from scrolling a delivered message
# away before the next poll and causing a duplicate resend.
TRANSCRIPT_CONFIRM_READ_LINES = 500
TRANSCRIPT_CONFIRM_POLL_ATTEMPTS = 6
TRANSCRIPT_CONFIRM_POLL_INTERVAL_S = 2.0
Target = Literal["main", "root-main", "worker"]
WORKER_TO_MAIN_INTENTS = frozenset({"question", "inform", "status"})
MAIN_TO_WORKER_INTENTS = frozenset({"inform", "redirect", "reply", "reply-retry", "control"})
PEER_INTENTS = frozenset({"question", "answer"})
SENTENCE_END_RE = re.compile(r"[.!?。！？]+(?=\s|$)")


@dataclass(frozen=True)
class Endpoint:
    target: Target
    pane_id: str
    expected_session_id: str | None
    expected_terminal_id: str | None
    agent_kind: str


class HerdrCommandError(ValueError):
    def __init__(self, command_args: list[str], returncode: int, stderr: str) -> None:
        self.command_args = tuple(command_args)
        self.returncode = returncode
        self.stderr = stderr.strip()
        self.error_code = self._error_code(self.stderr)
        super().__init__(
            f"herdr {' '.join(command_args)!r} failed (exit {returncode}): {self.stderr}"
        )

    @staticmethod
    def _error_code(stderr: str) -> str | None:
        try:
            payload = json.loads(stderr)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        error = payload.get("error")
        if not isinstance(error, dict):
            return None
        code = error.get("code")
        return code if isinstance(code, str) else None


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
        raise HerdrCommandError(args, result.returncode, result.stderr)
    return result.stdout


def run_herdr(args: list[str]) -> dict[str, Any]:
    stdout = run_herdr_raw(args)
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"herdr {' '.join(args)!r} returned non-JSON output") from exc


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


def resolve_endpoint(instruction: dict[str, Any], target: Target) -> Endpoint:
    if target == "main":
        pane_id = instruction.get("main_agent_herdr_pane_id")
        session_id = instruction.get("main_agent_session_id")
        terminal_id = instruction.get("main_agent_herdr_terminal_id")
        agent_kind = instruction.get("main_agent_kind")
    elif target == "root-main":
        pane_id = instruction.get("root_main_agent_herdr_pane_id")
        session_id = instruction.get("root_main_agent_session_id")
        terminal_id = instruction.get("root_main_agent_herdr_terminal_id")
        agent_kind = instruction.get("root_main_agent_kind")
    else:
        pane_id = instruction.get("herdr_pane_id")
        session_id = instruction.get("session_id")
        terminal_id = instruction.get("herdr_terminal_id")
        agent_kind = instruction.get("agent_kind")
    if not pane_id:
        raise ValueError(f"dispatch instruction has no {target} herdr pane")
    if agent_kind == "claude" and not session_id:
        raise ValueError(f"dispatch instruction has no {target} session fingerprint")
    if agent_kind == "codex" and not terminal_id:
        raise ValueError(f"dispatch instruction has no {target} terminal fingerprint")
    if agent_kind not in {"claude", "codex"}:
        raise ValueError(f"dispatch instruction has unsupported {target} agent kind")
    return Endpoint(
        target,
        str(pane_id),
        str(session_id) if session_id else None,
        str(terminal_id) if terminal_id else None,
        str(agent_kind),
    )


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
    agent = payload.get("result", {}).get("agent")
    if not isinstance(agent, dict) or agent.get("pane_id") != endpoint.pane_id:
        raise ValueError(
            f"{endpoint.target} live agent does not match pane {endpoint.pane_id!r}; "
            "refusing to send"
        )
    if endpoint.agent_kind == "codex":
        if agent.get("agent") != "codex":
            raise ValueError(
                f"{endpoint.target} agent kind mismatch for pane {endpoint.pane_id!r}: "
                f"expected 'codex', live {agent.get('agent')!r}; refusing to send"
            )
        live_terminal_id = agent.get("terminal_id")
        if live_terminal_id == endpoint.expected_terminal_id:
            return
        raise ValueError(
            f"{endpoint.target} terminal mismatch for pane {endpoint.pane_id!r}: "
            f"expected {endpoint.expected_terminal_id!r}, live {live_terminal_id!r}; "
            "refusing to send"
        )

    live_session = agent.get("agent_session")
    live_session_id = live_session.get("value") if isinstance(live_session, dict) else None
    if live_session_id == endpoint.expected_session_id:
        return
    if endpoint.agent_kind == "claude" and _claude_registry_corroborates(endpoint):
        return
    raise ValueError(
        f"{endpoint.target} session mismatch for pane {endpoint.pane_id!r}: "
        f"expected {endpoint.expected_session_id!r}, live {live_session_id!r}; refusing to send"
    )


def worker_endpoint_confirmed_closed(endpoint: Endpoint) -> bool:
    """True only when the recorded worker session is confirmed unreachable:
    herdr itself reports no live agent at this pane, or a live agent answers
    but its identity does not match what the dispatch recorded (pane closed
    and the index reused since -- the original worker is unreachable either
    way). False when the recorded worker still answers there.

    A separate bool predicate rather than a reuse of `validate_live_session`:
    that function raises on every mismatch, including a herdr transport
    failure (timeout, herdr missing, non-JSON output) that establishes
    nothing about whether the pane is actually closed. A caller deciding
    whether closed-pane recovery applies needs those told apart -- herdr
    saying "no agent here" decides yes, herdr being unreachable right now
    decides nothing and must propagate -- which a single raise/no-raise
    signal can't express.
    """
    try:
        payload = run_herdr(["agent", "get", endpoint.pane_id])
    except HerdrCommandError:
        return True
    agent = payload.get("result", {}).get("agent")
    if not isinstance(agent, dict) or agent.get("pane_id") != endpoint.pane_id:
        return True
    if endpoint.agent_kind == "codex":
        return not (
            agent.get("agent") == "codex"
            and agent.get("terminal_id") == endpoint.expected_terminal_id
        )
    live_session = agent.get("agent_session")
    live_session_id = live_session.get("value") if isinstance(live_session, dict) else None
    if live_session_id == endpoint.expected_session_id:
        return False
    if endpoint.agent_kind == "claude" and _claude_registry_corroborates(endpoint):
        return False
    return True


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


def validate_delta_message(message: str) -> str:
    text = message.strip()
    if not text:
        raise ValueError("message must be non-empty")
    endings = list(SENTENCE_END_RE.finditer(text))
    sentence_count = len(endings)
    if not endings or text[endings[-1].end() :].strip():
        sentence_count += 1
    sentence_count = max(sentence_count, len([line for line in text.splitlines() if line.strip()]))
    if sentence_count > 2:
        raise ValueError("live message must be delta-only and at most two sentences; use --ref for detail")
    return text


def normalize_references(references: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for reference in references:
        value = reference.strip()
        if not value:
            raise ValueError("--ref must be non-empty")
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


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
    references: tuple[str, ...],
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
        "reference_count": len(references),
        "reference_sha256": [
            hashlib.sha256(reference.encode()).hexdigest() for reference in references
        ],
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
    validate_live_session(endpoint)
    delivery_id = message_id or str(uuid.uuid4())
    reference_suffix = (
        f" refs={json.dumps(normalized_references, separators=(',', ':'))}"
        if normalized_references
        else ""
    )
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
                f"reply-to={sender_path}{reference_suffix}] {message}"
            )
        else:
            envelope = (
                f"[peer answer id={delivery_id} in-reply-to={in_reply_to} "
                f"from={sender_label}{reference_suffix}] {message}"
            )
    elif target in ("main", "root-main"):
        sender_role = "coworker" if target == "root-main" else "dispatched-agent"
        envelope = (
            f"[{sender_role} {intent} from={_dispatch_label(path, instruction)}"
            f"{reference_suffix}] {message}"
        )
    else:
        envelope = f"[main-agent {intent}{reference_suffix}] {message}"
    run_herdr(["agent", "prompt", endpoint.pane_id, envelope])
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
