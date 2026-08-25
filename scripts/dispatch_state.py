"""Shared paths and durable state for dispatched-agent scripts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def straw_boss_root() -> Path:
    return Path.home() / ".straw-boss"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


def contract_path(instruction_path: Path) -> Path:
    return instruction_path.with_name(
        f"{instruction_path.name.removesuffix('.json')}.contract.md"
    )


def launch_receipt_path(instruction_path: Path) -> Path:
    return instruction_path.with_name(
        f"{instruction_path.name.removesuffix('.json')}.launch.json"
    )


def standalone_status_path(instruction_path: Path) -> Path:
    return instruction_path.with_name(
        f"{instruction_path.name.removesuffix('.json')}.status.json"
    )


def plan_status_path(plan_slug: str, task_id: str) -> Path:
    return straw_boss_root() / "plans" / plan_slug / "status" / f"{task_id}.json"


def resolve_instruction_status_path(
    instruction_path: Path, instruction: dict[str, Any]
) -> Path:
    plan_id = instruction.get("plan_id")
    task_id = instruction.get("task_id")
    if plan_id is not None and task_id is not None:
        return plan_status_path(str(plan_id).removeprefix("p-"), str(task_id))
    return standalone_status_path(instruction_path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def render_dispatch_contract(instruction_path: Path) -> str:
    scripts_dir = Path(__file__).resolve().parent
    progress = scripts_dir / "report-progress.py"
    status = scripts_dir / "report-task-status.py"
    message = scripts_dir / "send-dispatch-message.py"
    return f"""# Straw Boss dispatched-agent contract

This contract is mandatory for this dispatched session.

- Your canonical instruction path is `{instruction_path}`.
- Do not use SendMessage, direct `herdr agent prompt`, pane ids, session ids, or
  agent names for cross-session communication.
- Report progress with:
  `uv run --script {progress} --instruction-path {instruction_path} --note \"<summary>\"`
- Send a question or coordination message to the main agent with:
  `uv run --script {message} --instruction-path {instruction_path} --to main --intent question --message \"<message>\"`
- If you cannot safely continue, report `awaiting-main-agent` with:
  `uv run --script {status} --instruction-path {instruction_path} --status awaiting-main-agent --note \"<what you need>\"`
- Before stopping, always report terminal `done` or `failed` with the same
  status script. Never finish work and become silently idle.
- After a checkpoint reply, continue the task. If another blocker appears,
  report a new checkpoint instead of waiting silently.
"""
