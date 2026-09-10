"""Herdr endpoint identity and live-session validation."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from straw_boss.dispatch.state import load_json


SUBPROCESS_TIMEOUT_S = 30
Target = Literal["main", "root-main", "worker", "orchestrator"]


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


def resolve_endpoint(instruction: dict[str, Any], target: Target) -> Endpoint:
    prefixes = {
        "main": "main_agent_",
        "root-main": "root_main_agent_",
        "worker": "",
    }
    prefix = prefixes[target]
    pane_id = instruction.get(f"{prefix}herdr_pane_id")
    session_id = instruction.get(f"{prefix}session_id")
    terminal_id = instruction.get(f"{prefix}herdr_terminal_id")
    agent_kind = instruction.get(f"{prefix}kind" if prefix else "agent_kind")
    if not pane_id:
        if target == "worker" and instruction.get("status") == "pending":
            raise ValueError(
                f"dispatch instruction has no {target} herdr pane -- it is still "
                "pending, so the coordinator has not run 'dispatch-task.py confirm' "
                "after launching. Ask the main agent to confirm the dispatch."
            )
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


def claude_registry_session(pane_id: str) -> str | None:
    """Resolve the interactive Claude session bound to this pane's foreground PID."""
    payload = run_herdr(["pane", "process-info", "--pane", pane_id])
    process_info = payload.get("result", {}).get("process_info")
    if not isinstance(process_info, dict) or process_info.get("pane_id") != pane_id:
        return None
    foreground_process_group_id = process_info.get("foreground_process_group_id")
    foreground_processes = process_info.get("foreground_processes")
    if (
        not isinstance(foreground_process_group_id, int)
        or isinstance(foreground_process_group_id, bool)
        or not isinstance(foreground_processes, list)
    ):
        raise ValueError(
            f"herdr process-info response for pane {pane_id!r} is missing or "
            "malformed foreground-process fields -- cannot determine corroboration"
        )
    candidates = [
        process
        for process in foreground_processes
        if _is_foreground_claude_process(process, foreground_process_group_id)
    ]
    if len(candidates) != 1:
        return None

    config_dir_value = os.environ.get("CLAUDE_CONFIG_DIR")
    config_dir = (
        Path(config_dir_value).expanduser()
        if config_dir_value
        else Path.home() / ".claude"
    )
    registry = load_json(
        config_dir / "sessions" / f"{foreground_process_group_id}.json"
    )
    if (
        isinstance(registry, dict)
        and registry.get("pid") == foreground_process_group_id
        and registry.get("kind") == "interactive"
        and registry.get("entrypoint") == "cli"
    ):
        session = registry.get("sessionId")
        return session if isinstance(session, str) and session.strip() else None
    return None


def _claude_registry_corroborates(endpoint: Endpoint) -> bool:
    return bool(endpoint.expected_session_id) and (
        claude_registry_session(endpoint.pane_id) == endpoint.expected_session_id
    )


def session_value(agent: dict[str, Any]) -> str | None:
    """Provider conversation identity, distinct from its current terminal."""
    session = agent.get("agent_session")
    if not isinstance(session, dict):
        return None
    if session.get("agent", agent.get("agent")) != agent.get("agent"):
        return None
    value = session.get("value")
    return value if isinstance(value, str) and value else None


def agent_matches_identity(
    agent: dict[str, Any], agent_kind: str,
    session_id: str | None, terminal_id: str | None,
) -> bool:
    """Use a recorded conversation id; terminal-only is legacy Codex identity."""
    if agent.get("agent") != agent_kind:
        return False
    if session_id:
        return session_value(agent) == session_id
    return bool(
        agent_kind == "codex" and terminal_id
        and agent.get("terminal_id") == terminal_id
    )


def validate_live_session(endpoint: Endpoint) -> str | None:
    payload = run_herdr(["agent", "get", endpoint.pane_id])
    agent = payload.get("result", {}).get("agent")
    if not isinstance(agent, dict) or agent.get("pane_id") != endpoint.pane_id:
        raise ValueError(
            f"{endpoint.target} live agent does not match pane {endpoint.pane_id!r}; refusing to send"
        )
    agent_status = agent.get("agent_status")
    agent_status = agent_status if isinstance(agent_status, str) else None
    if endpoint.agent_kind == "codex":
        if agent.get("agent") != "codex":
            raise ValueError(
                f"{endpoint.target} agent kind mismatch for pane {endpoint.pane_id!r}: "
                f"expected 'codex', live {agent.get('agent')!r}; refusing to send"
            )
        if agent_matches_identity(
            agent, endpoint.agent_kind, endpoint.expected_session_id, endpoint.expected_terminal_id
        ):
            return agent_status
        if endpoint.expected_session_id:
            raise ValueError(
                f"{endpoint.target} session mismatch for pane {endpoint.pane_id!r}: "
                f"expected {endpoint.expected_session_id!r}, live {session_value(agent)!r}; refusing to send"
            )
        raise ValueError(
            f"{endpoint.target} terminal mismatch for pane {endpoint.pane_id!r}: "
            f"expected {endpoint.expected_terminal_id!r}, live {agent.get('terminal_id')!r}; refusing to send"
        )

    live_session = agent.get("agent_session")
    live_session_id = live_session.get("value") if isinstance(live_session, dict) else None
    if live_session_id == endpoint.expected_session_id:
        return agent_status
    try:
        if _claude_registry_corroborates(endpoint):
            return agent_status
    except (ValueError, OSError):
        pass
    raise ValueError(
        f"{endpoint.target} session mismatch for pane {endpoint.pane_id!r}: "
        f"expected {endpoint.expected_session_id!r}, live {live_session_id!r}; refusing to send"
    )


def worker_endpoint_confirmed_closed(endpoint: Endpoint) -> bool:
    try:
        payload = run_herdr(["agent", "get", endpoint.pane_id])
        agent = payload.get("result", {}).get("agent")
    except HerdrCommandError as exc:
        if exc.error_code not in {"agent_not_found", "pane_not_found"}:
            raise
        agent = None
    if endpoint.agent_kind == "codex":
        if isinstance(agent, dict):
            if agent_matches_identity(
                agent, endpoint.agent_kind, endpoint.expected_session_id,
                endpoint.expected_terminal_id,
            ):
                return False
            if (agent.get("agent") == "codex"
                    and (not endpoint.expected_session_id or session_value(agent) is None)):
                raise ValueError("worker session is unavailable; cannot confirm closure")
        if endpoint.expected_session_id:
            # A live conversation may have moved away from its recorded route.
            agents = run_herdr(["agent", "list"]).get("result", {}).get("agents")
            if not isinstance(agents, list):
                raise ValueError("cannot confirm closure without a live agent list")
            return not any(
                isinstance(candidate, dict) and agent_matches_identity(
                    candidate, endpoint.agent_kind, endpoint.expected_session_id,
                    endpoint.expected_terminal_id,
                ) for candidate in agents
            )
        return True
    if not isinstance(agent, dict) or agent.get("pane_id") != endpoint.pane_id:
        return True
    if session_value(agent) == endpoint.expected_session_id:
        return False
    return not _claude_registry_corroborates(endpoint)


def validate_current_sender(endpoint: Endpoint) -> None:
    current_pane = os.environ.get("HERDR_PANE_ID")
    if current_pane != endpoint.pane_id:
        raise ValueError(
            f"sender pane mismatch: expected {endpoint.pane_id!r}, current {current_pane!r}; refusing to send"
        )
    validate_live_session(endpoint)


def validate_current_process_in_pane(pane_id: str) -> None:
    """Bind a destructive pane-scoped action to the caller's real process tree."""
    current_pane = os.environ.get("HERDR_PANE_ID")
    if current_pane != pane_id:
        raise ValueError(
            f"caller pane mismatch: expected {pane_id!r}, current {current_pane!r}"
        )
    payload = run_herdr(["pane", "process-info", "--pane", pane_id])
    info = payload.get("result", {}).get("process_info")
    if not isinstance(info, dict) or info.get("pane_id") != pane_id:
        raise ValueError(f"herdr could not resolve process identity for pane {pane_id!r}")
    foreground = info.get("foreground_processes")
    foreground_pids = (
        {
            process.get("pid")
            for process in foreground
            if isinstance(process, dict) and isinstance(process.get("pid"), int)
        }
        if isinstance(foreground, list)
        else set()
    )
    ancestors: set[int] = set()
    pid = os.getpid()
    for _ in range(64):
        if pid <= 1 or pid in ancestors:
            break
        ancestors.add(pid)
        try:
            result = subprocess.run(
                ["ps", "-o", "ppid=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("could not validate the caller process tree") from exc
        if result.returncode != 0 or not result.stdout.strip().isdigit():
            break
        pid = int(result.stdout.strip())
    if not foreground_pids.intersection(ancestors):
        raise ValueError(
            f"caller process is not running inside Herdr pane {pane_id!r}"
        )


def validate_status_sender(instruction_path: str | Path, status: str) -> None:
    path = Path(instruction_path).resolve()
    if not path.is_file():
        raise ValueError(f"no instruction file at {path}")
    instruction = load_json(path)
    if instruction.get("mode") != "herdr-pane":
        return
    source = resolve_endpoint(instruction, "main" if status == "cancelled" else "worker")
    validate_current_sender(source)
