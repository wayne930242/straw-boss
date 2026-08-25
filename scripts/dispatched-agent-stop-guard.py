#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Claude Stop hook: require a dispatched session to report before stopping."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from dispatch_state import (
    load_json,
    resolve_instruction_status_path,
    straw_boss_root,
)


VALID_REPORTED_STATUSES = {
    "done",
    "failed",
    "awaiting-authorization",
    "awaiting-user-input",
    "awaiting-main-agent",
    "cancelled",
}


def find_active_instruction(session_id: str) -> tuple[Path, dict[str, Any]] | None:
    dispatch_dir = straw_boss_root() / "dispatch"
    if not dispatch_dir.is_dir():
        return None
    for path in dispatch_dir.glob("*.json"):
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if (
            payload.get("session_id") == session_id
            and payload.get("status") == "in-progress"
            and "task" in payload
        ):
            return path, payload
    return None


def has_valid_report(instruction_path: Path, instruction: dict[str, Any]) -> bool:
    path = resolve_instruction_status_path(instruction_path, instruction)
    if not path.is_file():
        return False
    try:
        status = load_json(path).get("status")
    except (OSError, json.JSONDecodeError):
        return False
    return status in VALID_REPORTED_STATUSES


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    session_id = hook_input.get("session_id")
    if not session_id:
        return 0
    found = find_active_instruction(str(session_id))
    if found is None:
        return 0
    instruction_path, instruction = found
    if has_valid_report(instruction_path, instruction):
        return 0

    status_script = Path(__file__).resolve().parent / "report-task-status.py"
    reason = (
        "This dispatched session has not reported a checkpoint or terminal status. "
        "Continue working, or run the following command with one status chosen from "
        "done, failed, or awaiting-main-agent: "
        f"uv run --script {status_script} --instruction-path {instruction_path} "
        "--status <chosen-status> --note \"<summary or blocker>\""
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
