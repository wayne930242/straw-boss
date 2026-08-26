"""Shared paths and durable state for dispatched-agent scripts."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import uuid
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


def runtime_launcher_path() -> Path:
    return straw_boss_root() / "bin" / "run-straw-boss-script.py"


def _launcher_protocol(text: str) -> int:
    match = re.search(r"^RUNTIME_LAUNCHER_PROTOCOL = (\d+)$", text, re.MULTILINE)
    return int(match.group(1)) if match else -1


def install_runtime_launcher() -> Path:
    source = Path(__file__).resolve().parent / "run-straw-boss-script.py"
    source_text = source.read_text()
    destination = runtime_launcher_path()
    try:
        installed_text = destination.read_text()
    except OSError:
        installed_text = ""
    if _launcher_protocol(installed_text) >= _launcher_protocol(source_text):
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(source_text)
    temporary.replace(destination)
    return destination


def _uses_managed_plugin_cache(root: Path) -> bool:
    normalized = root.as_posix()
    return "/.claude/plugins/cache/" in normalized or "/.codex/plugins/cache/" in normalized


def render_dispatch_contract(
    instruction_path: Path,
    coworker_context: dict[str, Any] | None = None,
) -> str:
    origin_root = Path(__file__).resolve().parent.parent
    launcher = runtime_launcher_path()

    def command(script_name: str) -> str:
        parts = [
            "uv",
            "run",
            "--script",
            str(launcher),
            "--origin-root",
            str(origin_root),
        ]
        if _uses_managed_plugin_cache(origin_root):
            parts.append("--prefer-installed")
        parts.extend(["--script", script_name, "--"])
        return shlex.join(parts)

    progress = command("report-progress.py")
    status = command("report-task-status.py")
    message = command("send-dispatch-message.py")
    coworker_rules = ""
    if coworker_context is not None:
        writable_paths = coworker_context.get("coworker_writable_paths", [])
        if writable_paths:
            rendered_paths = ", ".join(f"`{path}`" for path in writable_paths)
            work_scope = (
                "- Your writable scope is limited to these repo-relative paths: "
                f"{rendered_paths}.\n"
            )
        else:
            work_scope = "- This is review-only: inspect and report without modifying files.\n"
        coworker_rules = f"""
- You are one direct coworker of another dispatched worker and share its exact
  worktree.
{work_scope}- Return your result to the parent through the status command; the parent owns
  integration and cleanup. Complete this task directly rather than coordinating
  another coworker.
"""
    return f"""# Straw Boss dispatched-agent contract

This contract is mandatory for this dispatched session.

- Your canonical instruction path is `{instruction_path}`.
- In `herdr-pane`, you are an independent agent after launch. You and the user
  choose the specification, design, implementation, and verification method.
  The main agent supplies the user requirement and integrated context and accepts
  those decisions.
{coworker_rules}
- Do not use SendMessage, direct `herdr agent prompt`, pane ids, session ids, or
  agent names for cross-session communication.
- Report progress with:
  `{progress} --instruction-path {shlex.quote(str(instruction_path))} --note '<summary>'`
- Live agent messages are delta-only and at most two sentences. Do not repeat
  identity, intent, history, or detailed evidence; add repeatable
  `--ref '<artifact/source>'` arguments for detail.
- Discuss work details and authorization directly with the user when this session
  is interactive. Ask the main agent only for integrated instructions/context or
  when this session has no direct user channel:
  `{message} --instruction-path {shlex.quote(str(instruction_path))} --to main --intent question --message '<delta>' [--ref '<source>']`
- If you must pause, choose the checkpoint that names who can unblock you:
  `awaiting-user-input` for a user-owned decision, `awaiting-main-agent` for
  coordination or action owned by the main agent, or `awaiting-authorization`
  only when an existing rule requires authorization for the next action. Report it with:
  `{status} --instruction-path {shlex.quote(str(instruction_path))} --status <checkpoint> --note '<what you need>' [--ref '<proof>']`
- Status notes follow the same two-sentence limit: state the outcome or exact
  unblock, and put verification detail in `--ref`.
- Before stopping, report terminal `done` or `failed` with the same status
  script; after persistence it notifies the main agent through Herdr.
- After a checkpoint reply, continue the task. If another blocker appears,
  report a new checkpoint instead of waiting silently.
"""
