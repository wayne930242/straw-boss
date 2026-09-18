"""Which provider sessions continue one another through context renewal.

A clear starts a new session id in the same pane for the same logical agent.
Adoption appends each old -> new hop here, so a question asked or received
before a renewal can still be answered after it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from straw_boss.dispatch.state import straw_boss_root


def lineage_path() -> Path:
    return straw_boss_root() / "renewal" / "lineage.jsonl"


def record_renewal(agent_kind: str, pane_id: str, old_session: str, new_session: str) -> None:
    path = lineage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "agent_kind": agent_kind,
        "pane_id": pane_id,
        "old_session_id": old_session,
        "new_session_id": new_session,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a") as stream:
        stream.write(json.dumps(entry) + "\n")


def session_lineage(session: str | None) -> set[str | None]:
    """This session and every session it continues."""
    predecessors: dict[str, str] = {}
    try:
        lines = lineage_path().read_text().splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict) and entry.get("new_session_id") and entry.get("old_session_id"):
            predecessors[str(entry["new_session_id"])] = str(entry["old_session_id"])
    found: set[str | None] = {session}
    while session in predecessors and predecessors[session] not in found:
        session = predecessors[session]
        found.add(session)
    return found
