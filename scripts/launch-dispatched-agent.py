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

from dispatch_state import dump_json, launch_receipt_path, load_json, sha256_text
from dispatch_transport import run_herdr


def live_agent(pane_id: str) -> dict[str, object]:
    payload = run_herdr(["agent", "get", pane_id])
    agent = payload.get("result", {}).get("agent")
    if not isinstance(agent, dict):
        raise ValueError(f"herdr could not resolve the launched agent in pane {pane_id!r}")
    return agent


def launch(
    instruction_path: str,
    name: str,
    pane_id: str,
    tab_id: str | None,
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
    provider_args = list(agent_args)
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
        provider_args = ["-c", f"developer_instructions={contract}", *provider_args]
    else:
        raise ValueError(f"unsupported agent kind {agent_kind!r}")

    run_herdr(
        ["agent", "start", name, "--kind", agent_kind, "--pane", pane_id, "--", *provider_args]
    )
    agent = live_agent(pane_id)
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
    agent = live_agent(pane_id)
    session_id = agent.get("agent_session", {}).get("value")
    if not session_id:
        raise ValueError("launched agent did not expose agent_session.value after its first prompt")
    if agent_kind == "claude" and session_id != instruction.get("session_id"):
        raise ValueError(
            f"launched Claude session {session_id!r} does not match preassigned session "
            f"{instruction.get('session_id')!r}"
        )

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
    parser.add_argument("--pane-id", required=True)
    parser.add_argument("--tab-id", default=None)
    parser.add_argument(
        "--agent-arg",
        action="append",
        default=[],
        help="additional provider argument; repeat once per argument",
    )
    args = parser.parse_args()
    try:
        result = launch(
            args.instruction_path, args.name, args.pane_id, args.tab_id, args.agent_arg
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
