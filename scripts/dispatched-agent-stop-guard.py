#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Claude Stop hook: require a dispatched session to report before stopping."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from straw_boss.dispatch.state import (
    load_json,
    resolve_instruction_status_path,
    straw_boss_root,
)
from straw_boss.renewal import current_record_path, payload_agent_kind, pending_record_from


TERMINAL_STATUSES = {"done", "failed", "cancelled"}
CHECKPOINT_STATUSES = {"awaiting-authorization", "awaiting-user-input", "awaiting-main-agent"}
VALID_REPORTED_STATUSES = TERMINAL_STATUSES | CHECKPOINT_STATUSES

# Markers a resolver stamps onto a checkpoint's status payload without
# changing `status` itself -- reply-to-worker.py's resolved_by_main_agent_at
# is the only one today. A payload carrying one of these is a stale
# checkpoint: the main agent already answered it, and the worker's own next
# report-task-status.py write (a full-file rewrite) drops the marker, so a
# fresh checkpoint counts as valid again.
RESOLUTION_MARKERS = ("resolved_by_main_agent_at",)


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
        payload = load_json(path)
    except (OSError, json.JSONDecodeError):
        return False
    status = payload.get("status")
    if status not in VALID_REPORTED_STATUSES:
        return False
    if status in TERMINAL_STATUSES:
        return True
    # A checkpoint the main agent already resolved is stale: the worker never
    # saw the reply become a fresh status, so it still owes one before it can
    # stop.
    return not any(marker in payload for marker in RESOLUTION_MARKERS)


def progress_log_path(instruction_path: Path) -> Path:
    stem = instruction_path.name.removesuffix(".json")
    return instruction_path.with_name(f"{stem}.progress.jsonl")


def fresh_wait(instruction_path: Path, instruction: dict[str, Any]) -> str | None:
    """Return what the worker is waiting on when its latest progress note,
    written after its latest status, records a wait on its own work."""
    progress_path = progress_log_path(instruction_path)
    try:
        lines = progress_path.read_text().splitlines()
        progress_mtime = progress_path.stat().st_mtime
    except OSError:
        return None
    entries = [line for line in lines if line.strip()]
    if not entries:
        return None
    try:
        waiting_on = json.loads(entries[-1]).get("waiting_on")
    except (json.JSONDecodeError, AttributeError):
        return None
    if not isinstance(waiting_on, str):
        return None
    status_path = resolve_instruction_status_path(instruction_path, instruction)
    try:
        if status_path.stat().st_mtime >= progress_mtime:
            return None
    except FileNotFoundError:
        pass
    return waiting_on


def consume_wait(instruction_path: Path, waiting_on: str) -> bool:
    # A wait covers the one stop that consumes it; this later entry makes the
    # next stop report again. An unconsumed wait would keep covering stops.
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": f"Turn ended waiting on: {waiting_on}",
    }
    try:
        with progress_log_path(instruction_path).open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        return False
    return True


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    session_id = hook_input.get("session_id") or hook_input.get("conversationId")
    if not session_id:
        return 0
    found = find_active_instruction(str(session_id))
    if found is None:
        return 0
    instruction_path, instruction = found
    if has_valid_report(instruction_path, instruction):
        return 0
    # A renewing worker checkpoints through its renewal record and progress log.
    if pending_record_from(
        current_record_path(hook_input, payload_agent_kind(hook_input)), str(session_id)
    ):
        return 0
    waiting_on = fresh_wait(instruction_path, instruction)
    if waiting_on is not None and consume_wait(instruction_path, waiting_on):
        return 0

    scripts_dir = Path(__file__).resolve().parent
    reason = (
        "This dispatched session has not reported a fresh checkpoint or terminal status "
        "(an earlier checkpoint the main agent already answered does not count). "
        "Continue working, or run the following command with one status chosen from "
        "done, failed, awaiting-main-agent, awaiting-user-input, or awaiting-authorization: "
        f"uv run --script {scripts_dir / 'report-task-status.py'} --instruction-path {instruction_path} "
        "--status <chosen-status> --note \"<summary or blocker>\". "
        "awaiting-main-agent is for a coordinator action or fact you need. "
        "When your own CI watch, subagent, review, or scheduled wake will resume this session, "
        "record that wait instead; it covers this one stop: "
        f"uv run --script {scripts_dir / 'report-progress.py'} --instruction-path {instruction_path} "
        "--note \"<summary>\" --waiting-on \"<what resumes you>\""
    )
    decision = "continue" if "conversationId" in hook_input else "block"
    print(json.dumps({"decision": decision, "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
