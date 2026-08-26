#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Start and prompt a herdr dispatched agent with its mandatory contract."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from dispatch_state import dump_json, launch_receipt_path, load_json, sha256_text
from dispatch_transport import run_herdr


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


def launch(
    instruction_path: str,
    name: str,
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

    agent_kind = str(instruction.get("agent_kind"))
    provider_args = provider_profile_args(instruction, agent_args)
    if agent_kind == "claude":
        provider_args = [
            "--session-id",
            str(instruction["session_id"]),
            "--name",
            name,
            "--append-system-prompt-file",
            str(contract_path),
            *provider_args,
        ]
    elif agent_kind == "codex":
        provider_args = [
            "-c",
            (
                "developer_instructions=Before any task action, read and follow "
                f"the mandatory contract at {contract_path}."
            ),
            *provider_args,
        ]
    else:
        raise ValueError(f"unsupported agent kind {agent_kind!r}")

    pane_id, tab_id = create_worker_pane(instruction)
    try:
        start_error: ValueError | None = None
        try:
            run_herdr(
                [
                    "agent",
                    "start",
                    name,
                    "--kind",
                    agent_kind,
                    "--pane",
                    pane_id,
                    "--",
                    *provider_args,
                ]
            )
        except ValueError as exc:
            start_error = exc

        try:
            agent = live_agent(pane_id)
        except ValueError:
            if start_error is not None:
                raise start_error
            raise
        if start_error is not None and agent.get("agent_status") != "blocked":
            raise start_error
        if agent.get("agent_status") == "blocked":
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

        run_herdr(["agent", "prompt", pane_id, str(instruction["task"])])
        session_id = wait_for_agent_session(pane_id)
        if agent_kind == "claude" and session_id != instruction.get("session_id"):
            raise ValueError(
                f"launched Claude session {session_id!r} does not match preassigned session "
                f"{instruction.get('session_id')!r}"
            )
    except ValueError as exc:
        try:
            run_herdr(["pane", "close", pane_id])
        except ValueError as close_error:
            raise ValueError(f"{exc}; worker-pane cleanup also failed: {close_error}") from exc
        raise

    receipt = {
        "instruction_path": str(inst_path),
        "contract_sha256": instruction["contract_sha256"],
        "agent_kind": agent_kind,
        "name": name,
        "pane_id": pane_id,
        "tab_id": tab_id,
        "session_id": str(session_id),
        "launched_at": datetime.now(timezone.utc).isoformat(),
    }
    receipt_path = launch_receipt_path(inst_path)
    dump_json(receipt_path, receipt)
    return {"launch_receipt_path": str(receipt_path), "launched": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruction-path", required=True)
    parser.add_argument("--name", required=True)
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
