"""Context renewal: measure a session's context, persist its continuity record,
and hand that record to the session a clear starts in the same pane.

Design: docs/specs/2026-09-17-orchestrator-context-renewal/design.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from straw_boss.dispatch.state import dump_json, load_json, straw_boss_root
from straw_boss.session_lineage import record_renewal


RENEWAL_THRESHOLD_TOKENS = 200_000
ROLES = ("main-agent", "dispatched-worker", "standalone-worker")
CLEAR_COMMAND = "/clear"
CONTINUE_PROMPT = "Continue from the context renewal record injected at session start."
# An agy Stop payload carries no continuation flag, so a block is remembered
# for this long; a stop inside the window is the same turn ending after it.
AGY_BLOCK_WINDOW_SECONDS = 600
UNBOUND_RECORD_MAX_AGE_SECONDS = 1800
UNSAFE_KEY_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


def renewal_root() -> Path:
    return straw_boss_root() / "renewal"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def payload_session(payload: dict[str, Any]) -> str | None:
    value = payload.get("session_id") or payload.get("conversationId")
    return str(value) if value else None


def payload_agent_kind(payload: dict[str, Any]) -> str:
    if payload.get("conversationId"):
        return "agy"
    transcript = payload.get("transcript_path")
    if isinstance(transcript, str) and Path(transcript).name.startswith("rollout-"):
        return "codex"
    return "claude"


def record_key(pane_id: str | None, cwd: str | None, agent_kind: str) -> str:
    """Herdr pane when there is one; outside Herdr, the working directory."""
    if pane_id:
        return f"pane-{UNSAFE_KEY_CHARS.sub('_', pane_id)}"
    digest = hashlib.sha256(f"{agent_kind}:{Path(cwd or '.').resolve()}".encode()).hexdigest()[:16]
    return f"cwd-{digest}"


def record_path(key: str) -> Path:
    return renewal_root() / f"{key}.json"


def current_record_path(payload: dict[str, Any], agent_kind: str) -> Path:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str):
        workspaces = payload.get("workspacePaths")
        cwd = workspaces[0] if isinstance(workspaces, list) and workspaces else os.getcwd()
    return record_path(record_key(os.environ.get("HERDR_PANE_ID"), cwd, agent_kind))


def load_record(path: Path) -> dict[str, Any] | None:
    try:
        return load_json(path)
    except (OSError, json.JSONDecodeError):
        return None


# --- context measurement ---------------------------------------------------


def _jsonl_reversed(path: Path) -> list[dict[str, Any]]:
    entries = []
    for line in reversed(path.read_text(errors="replace").splitlines()):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def claude_context_tokens(transcript: Path) -> int | None:
    for entry in _jsonl_reversed(transcript):
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        usage = (entry.get("message") or {}).get("usage")
        if isinstance(usage, dict):
            return sum(
                int(usage.get(field) or 0)
                for field in (
                    "input_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                )
            )
    return None


def codex_transcript_summary(transcript: Path) -> tuple[dict[str, Any] | None, bool]:
    """One parse of the transcript: the last `token_count` usage, and whether
    any row is a `compacted` entry (native auto-compact, or our own Jev
    registration on a candidate session)."""
    last_usage = None
    has_compacted = False
    for entry in _jsonl_reversed(transcript):
        if last_usage is None:
            body = entry.get("payload")
            if isinstance(body, dict) and body.get("type") == "token_count":
                last = (body.get("info") or {}).get("last_token_usage")
                if isinstance(last, dict) and "input_tokens" in last:
                    last_usage = last
        if entry.get("type") == "compacted":
            has_compacted = True
    return last_usage, has_compacted


def codex_last_token_usage(transcript: Path) -> dict[str, Any] | None:
    return codex_transcript_summary(transcript)[0]


def codex_context_tokens(transcript: Path) -> int | None:
    last = codex_last_token_usage(transcript)
    return int(last["input_tokens"]) if last else None


def codex_has_compacted_row(transcript: Path) -> bool:
    return codex_transcript_summary(transcript)[1]


def _varint(data: bytes, index: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        byte = data[index]
        index += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if byte < 0x80:
            return value, index


def _protobuf_fields(data: bytes) -> dict[int, list[int | bytes]]:
    fields: dict[int, list[int | bytes]] = {}
    index = 0
    while index < len(data):
        key, index = _varint(data, index)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, index = _varint(data, index)
        elif wire == 2:
            length, index = _varint(data, index)
            value = data[index : index + length]
            index += length
        elif wire == 5:
            value, index = int.from_bytes(data[index : index + 4], "little"), index + 4
        elif wire == 1:
            value, index = int.from_bytes(data[index : index + 8], "little"), index + 8
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")
        fields.setdefault(number, []).append(value)
    return fields


def agy_usage_tokens(generation_metadata: bytes) -> int | None:
    """Uncached (1.4.2) plus cached (1.4.5) input tokens of one agy generation.

    The layout is agy's undocumented conversation store; any mismatch reads as
    no measurement rather than a guess.
    """
    try:
        outer = _protobuf_fields(generation_metadata)
        usage = _protobuf_fields(next(v for v in outer[1] if isinstance(v, bytes)))
        counts = _protobuf_fields(next(v for v in usage[4] if isinstance(v, bytes)))
    except (KeyError, StopIteration, IndexError, ValueError):
        return None
    uncached = [v for v in counts.get(2, []) if isinstance(v, int)]
    cached = [v for v in counts.get(5, []) if isinstance(v, int)]
    if not uncached:
        return None
    return uncached[0] + (cached[0] if cached else 0)


def agy_context_tokens(conversation_id: str) -> int | None:
    database = (
        Path.home() / ".gemini" / "antigravity-cli" / "conversations" / f"{conversation_id}.db"
    )
    if not database.is_file():
        return None
    try:
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            row = connection.execute(
                "SELECT data FROM gen_metadata ORDER BY idx DESC LIMIT 1"
            ).fetchone()
    except sqlite3.Error:
        return None
    return agy_usage_tokens(row[0]) if row and row[0] else None


def context_tokens(payload: dict[str, Any], agent_kind: str) -> int | None:
    if agent_kind == "agy":
        conversation = payload.get("conversationId")
        return agy_context_tokens(str(conversation)) if conversation else None
    transcript = payload.get("transcript_path")
    if not isinstance(transcript, str) or not Path(transcript).is_file():
        return None
    if agent_kind == "codex":
        return codex_context_tokens(Path(transcript))
    return claude_context_tokens(Path(transcript))


# --- record lifecycle ------------------------------------------------------


def write_record(
    path: Path,
    *,
    pane_id: str | None,
    agent_kind: str,
    session_id: str,
    role: str,
    payload: str,
    instruction_paths: list[str],
) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"role must be one of {', '.join(ROLES)}")
    if not payload.strip():
        raise ValueError("the continuity payload on stdin is empty")
    for instruction in instruction_paths:
        if not Path(instruction).is_file():
            raise ValueError(f"no instruction file at {instruction}")
    record = {
        "pane_id": pane_id,
        "agent_kind": agent_kind,
        "session_id": session_id,
        "role": role,
        "payload": payload.strip(),
        "instruction_paths": [str(Path(p).resolve()) for p in instruction_paths],
        "status": "pending",
        "created_at": now_iso(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_json(path, record)
    return record


def pending_record_from(path: Path, session_id: str) -> dict[str, Any] | None:
    record = load_record(path)
    if record and record.get("status") == "pending" and record.get("session_id") == session_id:
        return record
    return None


def claimable_record(
    path: Path, agent_kind: str, session_id: str, source: object
) -> dict[str, Any] | None:
    """A pending record written by a previous session of this kind in this pane,
    or one a prior session in this pane consumed but never confirmed by
    reaching its own Stop -- a throwaway session that raced the real one to a
    clear cannot strand the record on itself; the next SessionStart reclaims it.

    Outside Herdr the key is only the working directory, so a record there is
    claimed only by a clear shortly after it was written, never by an
    unrelated session that later opens in the same directory.
    """
    record = load_record(path)
    if not (
        record
        and record.get("agent_kind") == agent_kind
        and record.get("pane_id") == os.environ.get("HERDR_PANE_ID")
    ):
        return None
    status = record.get("status")
    if status == "consumed":
        if (
            record.get("pane_id")
            and not record.get("confirmed")
            and record.get("consumed_by") != session_id
        ):
            return record
        return None
    if status != "pending" or record.get("session_id") == session_id:
        return None
    if record.get("pane_id"):
        return record
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(str(record.get("created_at")))
    except ValueError:
        return None
    if source == "clear" and age.total_seconds() <= UNBOUND_RECORD_MAX_AGE_SECONDS:
        return record
    return None


def consume_record(path: Path, record: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Claim the record for `session_id`, provisionally: `confirmed` only
    flips true once this session reaches its own Stop (context-renewal-guard.py).
    A prior claimant's session id survives as `reclaimed_from` so adoption can
    still find routes an abandoned claim already moved."""
    consumed = {
        **record,
        "status": "consumed",
        "consumed_by": session_id,
        "consumed_at": now_iso(),
        "confirmed": False,
    }
    if record.get("status") == "consumed" and record.get("consumed_by"):
        consumed["reclaimed_from"] = record["consumed_by"]
    dump_json(path, consumed)
    return consumed


# --- adoption --------------------------------------------------------------


def _dispatch_instructions() -> list[tuple[Path, dict[str, Any]]]:
    found = []
    for path in sorted((straw_boss_root() / "dispatch").glob("*.json")):
        if path.name.endswith((".launch.json", ".launch-failure.json", ".status.json")):
            continue
        try:
            instruction = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if "task" in instruction:
            found.append((path, instruction))
    return found


# Each role's routes as (field prefix, audit field). A main agent is also the
# root route of its dispatches' coworkers; a dispatched worker is also the main
# route of its own coworker.
RENEWAL_ROUTES = {
    "main-agent": (
        ("main_agent_", "main_agent_adoptions"),
        ("root_main_agent_", "root_main_agent_adoptions"),
    ),
    "dispatched-worker": (
        ("", "worker_adoptions"),
        ("main_agent_", "main_agent_adoptions"),
    ),
}


def adopt_renewed_session(record: dict[str, Any], new_session: str) -> list[str]:
    """Move the recorded session's dispatch routes to the renewed session.

    Only routes that still name the renewing session in this very pane move,
    so a record can never hand another pane's or another session's work over.
    `reclaimed_from` (set by consume_record on a reclaim) is preferred over the
    record's original session id, so routes an abandoned throwaway claim
    already moved are still found.
    """
    pane_id = record.get("pane_id")
    old_session = record.get("reclaimed_from") or record.get("session_id")
    routes = RENEWAL_ROUTES.get(record["role"])
    if not pane_id or not old_session or routes is None:
        return []
    adopted = []
    for path, instruction in _dispatch_instructions():
        updated = instruction
        for prefix, log_field in routes:
            session_field = f"{prefix}session_id"
            if (updated.get(f"{prefix}herdr_pane_id") != pane_id
                    or updated.get(session_field) != old_session):
                continue
            entry = {
                "at": now_iso(),
                "reason": "context-renewal",
                "before": {session_field: old_session},
                "after": {session_field: new_session},
            }
            updated = {
                **updated,
                session_field: new_session,
                log_field: [*updated.get(log_field, []), entry],
            }
        if updated is not instruction:
            dump_json(path, updated)
            adopted.append(str(path))
    record_renewal(record["agent_kind"], pane_id, old_session, new_session)
    _carry_message_ledger(record["agent_kind"], old_session, new_session)
    if record["role"] == "main-agent":
        _rekey_orchestrator_record(record["agent_kind"], old_session, new_session)
    return adopted


def _carry_message_ledger(agent_kind: str, old_session: str, new_session: str) -> None:
    """Append the old session's orchestrator message ledger to the renewed one,
    so questions it received before the clear stay answerable."""
    from straw_boss.dispatch.messages import delivery_ledger_path
    from straw_boss.orchestrator import record_path as orchestrator_record_path

    old_ledger = delivery_ledger_path(orchestrator_record_path(agent_kind, old_session))
    if not old_ledger.is_file():
        return
    new_ledger = delivery_ledger_path(orchestrator_record_path(agent_kind, new_session))
    with new_ledger.open("a") as stream:
        stream.write(old_ledger.read_text())
    old_ledger.unlink()


def _rekey_orchestrator_record(agent_kind: str, old_session: str, new_session: str) -> None:
    from straw_boss.orchestrator import record_path as orchestrator_record_path

    old_path = orchestrator_record_path(agent_kind, old_session)
    if not old_path.is_file():
        return
    entry = load_json(old_path)
    dump_json(
        orchestrator_record_path(agent_kind, new_session),
        {**entry, "session_id": new_session, "updated_at": now_iso()},
    )
    old_path.unlink(missing_ok=True)
