"""The immediate parent's execution ceiling for a coworker launch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from straw_boss.dispatch.permission import GUARDED_WRITE, READ_ONLY, UNRESTRICTED
from straw_boss.herdr.transport import run_herdr


def _effort_config(value: str) -> bool:
    key, separator, effort = value.partition("=")
    return bool(separator) and key == "model_reasoning_effort" and effort.strip().strip("\"'") in {
        "none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra",
    }


def effective_tier(kind: str, args: list[str]) -> str | None:
    """Recognize explicit launch policy; ambiguous/configured policy stays unknown."""
    values: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--":
            break
        flag, sep, value = token.partition("=")
        if kind == "codex" and len(token) > 2 and token[:2] in {"-s", "-c", "-p"}:
            flag, sep, value = token[:2], "=", token[2:].removeprefix("=")
        if flag in {"--config", "-c", "--profile", "-p"} or token.startswith("-c"):
            if not sep:
                index += 1
                value = args[index] if index < len(args) else ""
            if flag in {"--profile", "-p"} or not _effort_config(value):
                return None
        elif flag in {"--sandbox", "-s", "--permission-mode", "--mode"}:
            if not sep:
                index += 1
                value = args[index] if index < len(args) else ""
            tier = {
                "read-only": READ_ONLY, "plan": READ_ONLY, "manual": READ_ONLY,
                "workspace-write": GUARDED_WRITE, "default": GUARDED_WRITE,
                "acceptEdits": GUARDED_WRITE, "danger-full-access": UNRESTRICTED,
                "bypassPermissions": UNRESTRICTED,
            }.get(value)
            if tier is None:
                return None
            values.append(tier)
        elif flag in {"--dangerously-bypass-approvals-and-sandbox", "--yolo", "--dangerously-skip-permissions"}:
            values.append(UNRESTRICTED)
        elif flag == "--full-auto":
            values.append(GUARDED_WRITE)
        index += 1
    if not values:
        return GUARDED_WRITE if kind == "claude" else None
    if len(set(values)) != 1:
        return None
    return values[0]


def parent_permission_tier(parent: dict[str, Any]) -> str:
    """Use recorded effective arguments, or inspect a legacy parent's own pane."""
    recorded = parent.get("agent_permission_tier")
    if recorded in {READ_ONLY, GUARDED_WRITE, UNRESTRICTED}:
        return str(recorded)
    pane = str(parent["herdr_pane_id"])
    try:
        payload = run_herdr(["pane", "process-info", "--pane", pane])
    except ValueError:
        return READ_ONLY
    info = payload.get("result", {}).get("process_info", {})
    if not isinstance(info, dict) or info.get("pane_id") != pane:
        return READ_ONLY
    kind = str(parent["agent_kind"])
    candidates = []
    processes = info.get("foreground_processes")
    if not isinstance(processes, list):
        return READ_ONLY
    for process in processes:
        if not isinstance(process, dict):
            continue
        argv = process.get("argv")
        if isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv):
            if Path(argv[0]).name == kind:
                candidates.append(argv[1:])
    if len(candidates) != 1:
        return READ_ONLY
    return effective_tier(kind, candidates[0]) or READ_ONLY


def validate_coworker_args(kind: str, args: list[str]) -> None:
    """Keep execution policy in the inherited slot, with model/effort overrides."""
    allowed = {"--model", "-m", "--effort"}
    index = 0
    while index < len(args):
        flag, sep, value = args[index].partition("=")
        if flag not in allowed | {"-c", "--config"}:
            raise ValueError("coworker arguments support model and effort only; permissions inherit from the parent")
        if not sep:
            index += 1
            value = args[index] if index < len(args) else ""
        if not value or value.startswith("-"):
            raise ValueError("coworker provider option requires a value")
        if flag in {"-c", "--config"} and not _effort_config(value):
            raise ValueError("coworker config supports model_reasoning_effort only")
        index += 1
