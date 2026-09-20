"""Opt-in renewal ordering; a loaded hook must identify the current session."""
from __future__ import annotations

import json
import os
from pathlib import Path


def enabled(agent_kind: str, session: str) -> bool:
    return (agent_kind == "claude" and os.environ.get("STRAW_BOSS_JEV") == "1"
            and bool(os.environ.get("TYPESAFE_API_KEY", "").strip())
            and os.environ.get("STRAW_BOSS_JEV_READY_SESSION") == session)


def threshold() -> int:
    path = Path(__file__).resolve().parents[2] / "config" / "jev-policy.json"
    return int(json.loads(path.read_text())["renewal_threshold_tokens"])


def current_tokens(payload: dict) -> int | None:
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not Path(path).is_file():
        return None
    for line in reversed(Path(path).read_text(errors="replace").splitlines()):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
            return None
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        usage = (entry.get("message") or {}).get("usage")
        if isinstance(usage, dict):
            return sum(int(usage.get(field) or 0) for field in (
                "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return None
