"""Machine-local directory of live orchestrators and the deltas they exchange.

A coordinating session's identity has only ever existed inside the dispatches it
wrote (`main_agent_*` on each instruction), so an orchestrator that has not
dispatched yet is invisible to every other one on the machine -- `roll-call.py`
can only report it as an agent with no instruction of its own. This module keeps
one record per orchestrator, keyed on the provider conversation fingerprint that
dispatch delivery already validates identity with, so coordinators sharing a
machine can name each other, read each other's one-line scope, and send a
factual delta directly.

A record is a claim about a session, never a claim about a pane: `list` reports
a record whose fingerprint no live agent carries as `live: false` and keeps the
file, the same way `roll-call.py` refuses to read absence as permission to act.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dispatch_messages import (
    append_delivery_record,
    normalize_references,
    validate_delta_message,
    validate_peer_reply,
)
from dispatch_session import (
    Endpoint,
    HerdrCommandError,
    agent_matches_identity,
    run_herdr,
    session_value,
    validate_current_sender,
    validate_live_session,
)
from dispatch_state import dump_json, load_json, straw_boss_root
from dispatch_transport import (
    ENDPOINT_MISSING_ERROR_CODES,
    EndpointUnavailableError,
    prompt_delivery_args,
)


ORCHESTRATOR_INTENTS = ("inform", "question", "answer")
SUPPORTED_AGENT_KINDS = frozenset({"claude", "codex"})
MAX_SCOPE_CHARS = 200
# Long enough that yesterday's coordinator is still readable history, short
# enough that the directory keeps reading as who is coordinating now.
RETIRED_RECORD_TTL_DAYS = 7
UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


def registry_root() -> Path:
    return straw_boss_root() / "orchestrators"


def record_path(agent_kind: str, fingerprint: str) -> Path:
    return registry_root() / f"{agent_kind}-{UNSAFE_FILENAME_CHARS.sub('_', fingerprint)}.json"


def live_agents() -> list[dict[str, Any]]:
    payload = run_herdr(["agent", "list"])
    agents = payload.get("result", {}).get("agents")
    if not isinstance(agents, list):
        raise ValueError("herdr agent list did not return an agent list")
    return [agent for agent in agents if isinstance(agent, dict)]


def current_agent(agents: list[dict[str, Any]]) -> dict[str, Any]:
    pane_id = os.environ.get("HERDR_PANE_ID")
    if not pane_id:
        raise ValueError(
            "the orchestrator directory needs HERDR_PANE_ID; run this from inside a herdr pane"
        )
    for agent in agents:
        if str(agent.get("pane_id")) == pane_id:
            return agent
    raise ValueError(f"herdr has no live agent in pane {pane_id!r}")


def agent_identity(agent: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """This session's own (kind, session, terminal), read from herdr itself.

    The fingerprint a record is keyed on is whatever the delivery path validates
    on: the provider conversation id, or the terminal for a Codex agent whose
    Herdr build exposes no conversation id.
    """
    kind = agent.get("agent")
    if kind not in SUPPORTED_AGENT_KINDS:
        raise ValueError(f"unsupported agent kind {kind!r} for an orchestrator record")
    session = session_value(agent)
    terminal = agent.get("terminal_id")
    terminal = terminal if isinstance(terminal, str) and terminal else None
    if not session and not (kind == "codex" and terminal):
        raise ValueError(
            f"herdr exposes no session fingerprint for pane {agent.get('pane_id')!r}, "
            "so this orchestrator cannot be addressed"
        )
    return str(kind), session, terminal


def validate_scope(scope: str) -> str:
    text = scope.strip()
    if not text:
        raise ValueError("scope must be non-empty")
    if "\n" in text:
        raise ValueError("scope is one line naming this orchestrator's main work")
    if len(text) > MAX_SCOPE_CHARS:
        raise ValueError(f"scope is {len(text)} characters; keep it within {MAX_SCOPE_CHARS}")
    return text


def load_records() -> list[tuple[Path, dict[str, Any]]]:
    root = registry_root()
    if not root.is_dir():
        return []
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(root.glob("*.json")):
        try:
            records.append((path, load_json(path)))
        except (OSError, json.JSONDecodeError):
            continue
    return records


def live_match(
    record: dict[str, Any], agents: list[dict[str, Any]]
) -> dict[str, Any] | None:
    return next(
        (
            agent
            for agent in agents
            if agent_matches_identity(
                agent,
                str(record.get("agent_kind")),
                record.get("session_id"),
                record.get("herdr_terminal_id"),
            )
        ),
        None,
    )


def directory(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every record, reconciled against the live agents that carry them.

    The live agent supplies the current pane and name: a coordinator that moved
    panes is still the same session, and its recorded pane is the stale half.
    """
    rows: list[dict[str, Any]] = []
    for path, record in load_records():
        live = live_match(record, agents)
        rows.append(
            {
                "name": (live.get("name") if live else None) or record.get("name"),
                "agent_kind": record.get("agent_kind"),
                "scope": record.get("scope"),
                "cwd": (live.get("cwd") if live else None) or record.get("cwd"),
                "herdr_pane_id": (
                    str(live["pane_id"]) if live else record.get("herdr_pane_id")
                ),
                "session_id": record.get("session_id"),
                "herdr_terminal_id": record.get("herdr_terminal_id"),
                "agent_status": live.get("agent_status") if live else None,
                "live": live is not None,
                "updated_at": record.get("updated_at"),
                "record_path": str(path),
            }
        )
    return rows


def prune_retired(agents: list[dict[str, Any]]) -> list[str]:
    """Drop records whose session ended over a week ago.

    Their delivery ledger stays as history; only the address is removed, and
    only once no live agent has carried that fingerprint for the whole window.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETIRED_RECORD_TTL_DAYS)
    retired: list[str] = []
    for path, record in load_records():
        if live_match(record, agents) is not None:
            continue
        try:
            updated = datetime.fromisoformat(str(record.get("updated_at")))
        except (TypeError, ValueError):
            continue
        if updated.tzinfo is not None and updated < cutoff:
            path.unlink(missing_ok=True)
            retired.append(str(path))
    return retired


def register(scope: str) -> dict[str, Any]:
    scope = validate_scope(scope)
    agents = live_agents()
    agent = current_agent(agents)
    kind, session, terminal = agent_identity(agent)
    path = record_path(kind, session or str(terminal))
    previous = load_json(path) if path.is_file() else None
    now = datetime.now(timezone.utc).isoformat()
    name = agent.get("name")
    cwd = agent.get("cwd")
    record = {
        "agent_kind": kind,
        "session_id": session,
        "herdr_terminal_id": terminal,
        "herdr_pane_id": str(agent.get("pane_id")),
        "name": name if isinstance(name, str) and name else None,
        "cwd": str(cwd) if isinstance(cwd, str) and cwd else None,
        "scope": scope,
        "registered_at": (previous or {}).get("registered_at", now),
        "updated_at": now,
    }
    registry_root().mkdir(parents=True, exist_ok=True)
    dump_json(path, record)
    # A Codex session first registered by terminal id and later exposing a
    # conversation id would otherwise leave a second record addressing this
    # same live agent. Only records this very agent answers to are removed.
    for other_path, other in load_records():
        if other_path != path and live_match(other, [agent]) is not None:
            other_path.unlink(missing_ok=True)
    retired = prune_retired(agents)
    return {
        "record_path": str(path),
        "record": record,
        "retired": retired,
        "directory": directory(agents),
    }


def resolve_target(address: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    matches = [
        row
        for row in rows
        if address in {row["name"], row["herdr_pane_id"], row["session_id"]}
    ]
    if not matches:
        raise ValueError(f"no registered orchestrator matches {address!r}")
    if len(matches) > 1:
        raise ValueError(
            f"{address!r} matches {len(matches)} registered orchestrators; address one by pane id"
        )
    return matches[0]


def row_endpoint(row: dict[str, Any]) -> Endpoint:
    return Endpoint(
        "orchestrator",
        str(row["herdr_pane_id"]),
        row["session_id"],
        row["herdr_terminal_id"],
        str(row["agent_kind"]),
    )


def format_envelope(
    *,
    intent: str,
    delivery_id: str,
    sender: str,
    sender_pane_id: str,
    in_reply_to: str | None,
    references: tuple[str, ...],
    message: str,
) -> str:
    """The receiving orchestrator's whole route back: who sent this, and the
    herdr pane to answer on."""
    parts = [
        f"orchestrator {intent}",
        f"id={delivery_id}",
        f"from={sender}",
        f"pane={sender_pane_id}",
    ]
    if in_reply_to:
        parts.append(f"in-reply-to={in_reply_to}")
    if references:
        parts.append(f"refs={json.dumps(references, separators=(',', ':'))}")
    return f"[{' '.join(parts)}] {message}"


def send(
    *,
    to: str,
    intent: str,
    message: str,
    message_id: str,
    in_reply_to: str | None = None,
    references: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    if intent not in ORCHESTRATOR_INTENTS:
        raise ValueError(f"orchestrator intent {intent!r} is not allowed")
    if intent == "answer" and not in_reply_to:
        raise ValueError("an orchestrator answer requires --in-reply-to")
    if intent != "answer" and in_reply_to:
        raise ValueError("only an orchestrator answer carries --in-reply-to")
    text = validate_delta_message(message)
    normalized_references = normalize_references(references)

    agents = live_agents()
    agent = current_agent(agents)
    kind, session, terminal = agent_identity(agent)
    my_path = record_path(kind, session or str(terminal))
    if not my_path.is_file():
        raise ValueError(
            "this orchestrator is unregistered; run register-orchestrator.py --scope first"
        )
    my_record = load_json(my_path)
    source = Endpoint("orchestrator", str(agent.get("pane_id")), session, terminal, kind)

    rows = directory(agents)
    target = resolve_target(to, rows)
    if target["record_path"] == str(my_path):
        raise ValueError("an orchestrator message needs another orchestrator as its target")
    target_path = Path(target["record_path"])
    endpoint = row_endpoint(target)

    validate_current_sender(source)
    if intent == "answer":
        assert in_reply_to is not None
        validate_peer_reply(my_path, source, endpoint, in_reply_to)

    def record_undelivered(reason: str) -> None:
        append_delivery_record(
            target_path,
            source,
            endpoint,
            intent,
            text,
            message_id,
            in_reply_to,
            normalized_references,
            undeliverable_reason=reason,
        )

    if not target["live"]:
        reason = f"no live agent carries the session registered as {to!r}"
        record_undelivered(reason)
        raise EndpointUnavailableError(
            f"{reason}; the message is recorded undelivered in its delivery ledger "
            f"as {message_id}"
        )
    try:
        pre_send_status = validate_live_session(endpoint)
    except HerdrCommandError as exc:
        if exc.error_code not in ENDPOINT_MISSING_ERROR_CODES:
            raise
        record_undelivered(str(exc))
        raise EndpointUnavailableError(
            f"the target orchestrator's session is no longer live ({exc}); the message "
            f"is recorded undelivered in its delivery ledger as {message_id}"
        ) from exc

    envelope = format_envelope(
        intent=intent,
        delivery_id=message_id,
        sender=agent.get("name") or my_record.get("name") or source.pane_id,
        sender_pane_id=source.pane_id,
        in_reply_to=in_reply_to,
        references=normalized_references,
        message=text,
    )
    run_herdr(prompt_delivery_args(endpoint.pane_id, envelope, pre_send_status))
    append_delivery_record(
        target_path,
        source,
        endpoint,
        intent,
        text,
        message_id,
        in_reply_to,
        normalized_references,
    )
    return {
        "submitted": True,
        "message_id": message_id,
        "to": target["name"] or target["herdr_pane_id"],
        "target_pane_id": endpoint.pane_id,
    }
