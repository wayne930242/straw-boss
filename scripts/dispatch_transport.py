"""Session-validating herdr transport for every dispatch direction."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from dispatch_state import load_json


SUBPROCESS_TIMEOUT_S = 30
Target = Literal["main", "worker"]


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


def append_delivery_record(
    instruction_path: Path, endpoint: Endpoint, intent: str, message: str
) -> None:
    path = instruction_path.with_name(
        f"{instruction_path.name.removesuffix('.json')}.messages.jsonl"
    )
    record = {
        "direction": f"to-{endpoint.target}",
        "intent": intent,
        "target_session_id": endpoint.expected_session_id,
        "message_sha256": hashlib.sha256(message.encode()).hexdigest(),
        "message_length": len(message),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a") as stream:
        stream.write(json.dumps(record) + "\n")


def send_instruction_message(
    instruction_path: str | Path, target: Target, intent: str, message: str
) -> Endpoint:
    path = Path(instruction_path).resolve()
    if not path.is_file():
        raise ValueError(f"no instruction file at {path}")
    instruction = load_json(path)
    endpoint = resolve_endpoint(instruction, target)
    validate_live_session(endpoint)
    if intent == "control":
        if target != "worker" or not message.startswith("/"):
            raise ValueError("control intent requires a worker target and a slash command")
        envelope = message
    else:
        envelope = f"[Straw Boss {intent} to {target}] {message}"
    run_herdr(["agent", "prompt", endpoint.pane_id, envelope])
    append_delivery_record(path, endpoint, intent, message)
    return endpoint
