"""Recognize a Claude Code process that pi runs as its model backend.

pi-claude-bridge drives Claude Code through the Agent SDK, and a bridge that
loads the user's settings loads this plugin's hooks with them. Pi owns that
session, its context, and its coordination, so no hook acts there: priming
would cast pi's model as a Claude Code main agent, and a Stop block would ask
it to renew or report through scripts pi never runs.
"""

from __future__ import annotations

import os
from collections.abc import Mapping


def inside_pi(env: Mapping[str, str] = os.environ) -> bool:
    """Pi marks its own process with PI_CODING_AGENT=true, which the SDK child
    inherits, and the SDK marks that child with an sdk-* entrypoint. Both are
    required: a claude CLI that inherited pi's own environment, say through a
    Herdr server pi started, is still an ordinary Straw Boss session. Claude Code
    keeps an inherited entrypoint, so a CLI started from inside the SDK child
    (AskClaude's own Bash tool) still matches.
    """
    return (env.get("PI_CODING_AGENT") == "true"
            and env.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk"))
