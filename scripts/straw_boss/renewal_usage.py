"""Comparable per-renewal Codex usage, independent of whether Jev ran.

Design: docs/specs/2026-09-21-codex-renewal-usage-records/design.md.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import Any

from . import jev_renewal
from . import renewal
from .jev_private import private_read, root as jev_root


def usage_path() -> Path:
    return renewal.renewal_root() / "codex-usage.jsonl"


def _lock_path() -> Path:
    return renewal.renewal_root() / "codex-usage.lock"


def append(entry: dict[str, Any]) -> None:
    path = usage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path()
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with path.open("a") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            file.flush()
            os.fsync(file.fileno())


def _triple(usage: dict[str, Any] | None) -> dict[str, Any] | None:
    if not usage:
        return None
    return {
        "input_tokens": usage.get("input_tokens"),
        "cached_input_tokens": usage.get("cached_input_tokens"),
        "output_tokens": usage.get("output_tokens"),
    }


def _off_reason() -> str:
    if os.environ.get("STRAW_BOSS_JEV") != "1":
        return "disabled"
    return "blank-api-key"


def classify(continuity: dict[str, Any], session: str) -> tuple[str, str | None, dict[str, Any] | None]:
    """Which renewal path ran, its reason, and the archived Jev record if any."""
    jev_request = continuity.get("jev_request")
    if not jev_request:
        if jev_renewal.enabled("codex", continuity.get("session_id") or session):
            return "jev-failure", "schedule-failed", None
        return "ordinary-jev-off", _off_reason(), None
    request = json.loads(private_read(Path(jev_request)))
    archived_path = jev_root() / "runs" / f"{request['run_id']}.json"
    archived = json.loads(private_read(archived_path))["record"]
    decision = archived.get("decision")
    reason = archived.get("fallback_reason")
    if decision == "apply":
        return "jev-applied", None, archived
    if reason in {"unchanged-candidate", "under-reduction-gate"}:
        return "jev-gate-miss", reason, archived
    return "jev-failure", reason, archived


def _jev_block(archived: dict[str, Any]) -> dict[str, Any]:
    jev = archived.get("jev") or {}
    measurement = archived.get("measurement") or {}
    return {
        "run_id": archived.get("run_id"),
        "model": jev.get("model"),
        "requests": jev.get("requests"),
        "input_tokens": jev.get("input_tokens"),
        "latency_ms": jev.get("latency_ms"),
        "gate_reduction_pct": archived.get("gate_reduction_pct"),
        "probe": {
            "baseline_resume_usage": _triple(measurement.get("baseline_resume_usage")),
            "candidate_resume_usage": _triple(measurement.get("candidate_resume_usage")),
        },
    }


def record_renewal(continuity: dict[str, Any], session: str, transcript: Path) -> None:
    """Append one comparable usage line for the renewal that produced `session`.

    Called once, at the renewed session's own first Stop; the caller gates
    on `usage_recorded` so a later Stop in the same session is a no-op here.
    """
    usage = renewal.codex_last_token_usage(transcript)
    if usage is None:
        return
    path, reason, archived = classify(continuity, session)
    append({
        "schema_version": 1,
        "kind": "renewal",
        "recorded_at": renewal.now_iso(),
        "path": path,
        "path_reason": reason,
        "pane_id": continuity.get("pane_id"),
        "role": continuity.get("role"),
        "old_session_id": continuity.get("session_id"),
        "new_session_id": session,
        "jev": _jev_block(archived) if archived is not None else None,
        "post_renewal": {"window": "first-stop-of-renewed-session", **_triple(usage)},
    })


def _native_compaction_marker(session: str) -> Path:
    return renewal.renewal_root() / "native-compaction-seen" / renewal.UNSAFE_KEY_CHARS.sub("_", session)


def record_native_compaction(session: str, pane_id: str | None, transcript: Path) -> None:
    """Best-effort: a `compacted` row in a non-candidate session's own
    rollout is native auto-compact, since our system never writes that row
    type anywhere but a Jev candidate session's own file. Records the
    post-compaction snapshot once per session; the pre-compaction peak that
    crossed 300k is not captured."""
    marker = _native_compaction_marker(session)
    if marker.is_file() or not renewal.codex_has_compacted_row(transcript):
        return
    usage = renewal.codex_last_token_usage(transcript)
    append({
        "schema_version": 1,
        "kind": "native-300k-compaction",
        "recorded_at": renewal.now_iso(),
        "session_id": session,
        "pane_id": pane_id,
        "post_compaction": _triple(usage),
        "limitation": "post-compaction snapshot only; the pre-compaction peak that crossed 300k is not captured",
    })
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
