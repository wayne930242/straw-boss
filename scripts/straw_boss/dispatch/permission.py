"""The main agent's restriction tier, and its flags for each agent kind.

`dispatching-work`'s permission mapping requires a dispatched agent to mirror
the main agent's restriction tier and never exceed it. That requirement lived
only in prose, so every caller had to remember to pass the flag by hand -- and
a caller that forgot launched a worker that stops to ask about everything,
which is exactly what the mirroring exists to prevent.
"""

from __future__ import annotations

import os
import subprocess

UNRESTRICTED = "unrestricted"
GUARDED_WRITE = "guarded-write"
READ_ONLY = "read-only"

# A caller's deliberate "launch with no permission flag at all", as opposed to a
# tier that could not be read. Both add no flags; only this one says so on
# purpose, which is what the archived instruction has to be able to show.
NO_MIRROR = "none"

# Every flag that sets a provider's permission posture. Mirroring fills one
# slot, so a caller writing any of these for itself replaces the mirrored flag
# rather than stacking a second, conflicting one beside it.
PERMISSION_FLAGS: dict[str, tuple[str, ...]] = {
    "claude": ("--dangerously-skip-permissions", "--permission-mode"),
    "codex": (
        "--dangerously-bypass-approvals-and-sandbox",
        "--sandbox",
        "--ask-for-approval",
    ),
    "agy": ("--dangerously-skip-permissions", "--mode", "--sandbox"),
    "antigravity": ("--dangerously-skip-permissions", "--mode", "--sandbox"),
}

# skills/dispatching-work/references/dispatch-mechanics.md's "Permission mapping".
# A kind absent from a tier has no documented flag: the launcher leaves it at the
# provider default, which is never more permissive than the tier being mirrored.
TIER_FLAGS: dict[str, dict[str, tuple[str, ...]]] = {
    UNRESTRICTED: {
        "claude": ("--dangerously-skip-permissions",),
        "codex": ("--dangerously-bypass-approvals-and-sandbox",),
        "agy": ("--dangerously-skip-permissions",),
        "antigravity": ("--dangerously-skip-permissions",),
    },
    GUARDED_WRITE: {
        "codex": ("--sandbox", "workspace-write", "--ask-for-approval", "on-request"),
    },
    READ_ONLY: {
        "claude": ("--permission-mode", "plan"),
        "codex": ("--sandbox", "read-only"),
        "agy": ("--mode", "plan"),
        "antigravity": ("--mode", "plan"),
    },
}


_USE_ENV = object()


def detect_claude_tier(pid: str | None | object = _USE_ENV) -> str | None:
    """The restriction tier of a running Claude main agent, or None if unreadable.

    None means "could not read", not "unrestricted" -- the caller decides what an
    unknown tier means rather than having a default silently chosen here.

    Omitting `pid` reads this session's own `CLAUDE_PID`. Passing one explicitly
    never falls back to the environment: a caller that hands over a blank or bad
    pid is asking about a specific process, and answering with the ambient
    session's tier would attribute one agent's permissions to another.
    """
    if pid is _USE_ENV:
        pid = os.environ.get("CLAUDE_PID")
    if not isinstance(pid, str) or not pid.isdigit():
        return None
    try:
        args = subprocess.run(
            ["ps", "-p", pid, "-ww", "-o", "args="],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    if not args.strip():
        return None
    tokens = args.split()
    if "--dangerously-skip-permissions" in tokens:
        return UNRESTRICTED
    if "--permission-mode" in tokens:
        index = tokens.index("--permission-mode")
        mode = tokens[index + 1] if index + 1 < len(tokens) else ""
        if mode in {"plan", "manual"}:
            return READ_ONLY
        return GUARDED_WRITE
    return GUARDED_WRITE


def tier_flags(tier: str | None, agent_kind: str) -> tuple[str, ...]:
    """Flags that put `agent_kind` at `tier`, or empty when none is documented."""
    if tier is None:
        return ()
    return TIER_FLAGS.get(tier, {}).get(agent_kind, ())


def permission_flags(agent_kind: str) -> tuple[str, ...]:
    """Every flag that sets `agent_kind`'s permission posture."""
    return PERMISSION_FLAGS.get(agent_kind, ())
