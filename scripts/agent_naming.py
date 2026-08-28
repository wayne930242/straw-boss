"""Herdr agent-name rules shared by the launcher and `check-agent-name.py`.

A name is a display convenience only -- confirm/receipt identity binding never
depends on it (see `dispatch_state.py`'s contract text: "Do not use ... agent
names for cross-session communication").
"""

from __future__ import annotations

import re
from typing import Any

NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
MAX_NAME_LENGTH = 32


def live_names(agent_list_payload: dict[str, Any]) -> set[str]:
    try:
        agents = agent_list_payload["result"]["agents"]
    except KeyError as exc:
        raise ValueError(f"unexpected 'herdr agent list' shape -- missing {exc}") from exc
    return {a["name"] for a in agents if "name" in a}


def _slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", text.strip().lower()).strip("-")
    if not slug or not slug[0].isalpha():
        slug = f"a{slug}"
    return slug


def derive_agent_name(role: str, app: str) -> str:
    """Compose `<app>-<role>`, truncating the app signal to fit the cap.

    `role` (e.g. "coordinator", "worker", "coworker") is kept whole -- it says
    what the agent is; `app` says which workroom, and is the part that gives on
    a long name.
    """
    budget = MAX_NAME_LENGTH - len(role) - 1
    if budget < 1:
        raise ValueError(f"role {role!r} leaves no room for an app-derived name")
    app_slug = _slug(app)[:budget].rstrip("-")
    name = f"{app_slug}-{role}"
    if not NAME_PATTERN.match(name):
        raise ValueError(
            f"derived agent name {name!r} does not match {NAME_PATTERN.pattern}"
        )
    return name


def unique_agent_name(candidate: str, taken: set[str]) -> str:
    if candidate not in taken:
        return candidate
    n = 2
    while True:
        suffix = f"-{n}"
        attempt = f"{candidate[: MAX_NAME_LENGTH - len(suffix)].rstrip('-')}{suffix}"
        if attempt not in taken:
            return attempt
        n += 1
