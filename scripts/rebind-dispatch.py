#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Rebind one resumed Codex dispatch using explicitly verified original sessions.

Pass original session ids from the launch-era provider logs, plus --ref evidence.
This command validates the coordinator process and both live conversations; it
changes only routing metadata. It never reports task status or sends a message.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from straw_boss.herdr.session import (
    Endpoint, agent_matches_identity, resolve_endpoint, run_herdr,
    validate_current_process_in_pane, validate_live_session,
)
from straw_boss.dispatch.state import dump_json, launch_receipt_path, load_json


def verify_original_sessions(path: Path, instruction: dict, sessions: dict[str, str],
                             references: list[str]) -> None:
    """Corroborate legacy ids against launch-era Codex rollout records."""
    receipt = load_json(launch_receipt_path(path))
    if (Path(str(receipt.get("instruction_path", ""))).resolve() != path
            or receipt.get("contract_sha256") != instruction.get("contract_sha256")):
        raise ValueError("launch receipt does not bind this instruction and contract")
    launched = datetime.fromisoformat(receipt["launched_at"])
    verified = set()
    for reference in references:
        with Path(reference).expanduser().open() as stream:
            first = json.loads(next(stream))
            meta = first.get("payload", {})
            if first.get("type") != "session_meta":
                continue
            targets = [target for target, session in sessions.items() if meta.get("id") == session]
            if not targets or datetime.fromisoformat(meta["timestamp"].replace("Z", "+00:00")) > launched:
                continue
            launch_calls = set()
            for line in stream:
                event = json.loads(line)
                payload = event.get("payload", {})
                if event.get("type") != "response_item":
                    continue
                serialized = json.dumps(payload, ensure_ascii=False)
                # The worker's initial developer context carries the immutable
                # contract path before any user prompt could introduce a reference.
                if "worker" in targets and "worker" not in verified:
                    if payload.get("role") == "user":
                        targets.remove("worker")
                    elif payload.get("role") == "developer" and instruction["contract_path"] in serialized:
                        verified.add("worker")
                if "main" in targets and "main" not in verified:
                    timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                    if (payload.get("type") in {"function_call", "custom_tool_call"}
                            and timestamp <= launched and "dispatch-task.py" in serialized
                            and "write" in serialized and payload.get("call_id")):
                        launch_calls.add(payload["call_id"])
                    if ((timestamp <= launched or payload.get("call_id") in launch_calls)
                            and payload.get("type") in {"function_call_output", "custom_tool_call_output"}
                            and receipt["instruction_path"] in serialized
                            and instruction["contract_sha256"] in serialized):
                        verified.add("main")
                if all(target in verified for target in targets):
                    break
    if verified != {"main", "worker"}:
        raise ValueError("original-session evidence does not bind both launch-era conversations")


def rebind(instruction_path: str, main_session_id: str, worker_session_id: str,
           references: list[str]) -> dict[str, object]:
    path = Path(instruction_path).resolve()
    instruction = load_json(path)
    if instruction.get("mode") != "herdr-pane" or instruction.get("status") != "in-progress":
        raise ValueError("rebind requires an in-progress interactive dispatch")
    if instruction.get("parent_instruction_path"):
        raise ValueError("rebind the top-level dispatch first; coworker routes require separate evidence")
    if not references or any(not value.strip() for value in references):
        raise ValueError("--ref must identify the original-session evidence")
    if not main_session_id.strip() or not worker_session_id.strip():
        raise ValueError("original main and worker session ids are required")
    endpoints = {target: resolve_endpoint(instruction, target) for target in ("main", "worker")}
    if any(endpoint.agent_kind != "codex" for endpoint in endpoints.values()):
        raise ValueError("this recovery command requires a Codex main agent and worker")
    validate_current_process_in_pane(endpoints["main"].pane_id)
    verify_original_sessions(path, instruction, {
        "main": main_session_id, "worker": worker_session_id,
    }, references)
    changes = {}
    for target, supplied_session in (("main", main_session_id), ("worker", worker_session_id)):
        previous = endpoints[target]
        if previous.expected_session_id and previous.expected_session_id != supplied_session:
            raise ValueError(f"{target} original session differs from the recorded session")
        candidate = Endpoint(target, previous.pane_id, supplied_session,
                             previous.expected_terminal_id, previous.agent_kind)
        # Capture and validate the same snapshot before writing its terminal.
        agent = run_herdr(["agent", "get", candidate.pane_id]).get("result", {}).get("agent")
        if (not isinstance(agent, dict) or agent.get("pane_id") != candidate.pane_id
                or not agent_matches_identity(agent, "codex", supplied_session, None)):
            raise ValueError(f"{target} identity changed during rebind")
        terminal = agent.get("terminal_id")
        if not isinstance(terminal, str) or not terminal:
            raise ValueError(f"{target} has no live terminal id")
        prefix = "main_agent_" if target == "main" else ""
        changes[f"{prefix}session_id"] = supplied_session
        changes[f"{prefix}herdr_terminal_id"] = terminal
    # Re-check caller/targets after all evidence has been collected.
    candidate_instruction = {**instruction, **changes}
    for target in ("main", "worker"):
        validate_live_session(resolve_endpoint(candidate_instruction, target))
    if load_json(path) != instruction:
        raise ValueError("instruction changed during rebind; retry from fresh state")
    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "refs": references,
        "before": {key: instruction.get(key) for key in changes},
        "after": changes,
    }
    candidate_instruction["routing_rebindings"] = [*instruction.get("routing_rebindings", []), record]
    dump_json(path, candidate_instruction)
    return {"rebound": True, "instruction_path": str(path), "sessions": {
        "main": main_session_id, "worker": worker_session_id,
    }}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruction-path", required=True)
    parser.add_argument("--main-session-id", required=True)
    parser.add_argument("--worker-session-id", required=True)
    parser.add_argument("--ref", action="append", required=True)
    args = parser.parse_args()
    try:
        result = rebind(args.instruction_path, args.main_session_id, args.worker_session_id, args.ref)
    except (ValueError, OSError, KeyError, StopIteration) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
