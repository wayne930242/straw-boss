#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Validates a candidate worker-agent name before the main agent runs
`herdr agent start` (see skills/dispatching-work/references/dispatch-mechanics.md
and plan-mechanics.md).

Checks the two things a hand-done check tends to get wrong:
  - format: must match ^[A-Za-z][A-Za-z0-9_-]{0,31}$
  - uniqueness: must not already be a `name` among live herdr agents

Never calls `herdr` itself -- the main agent runs `herdr agent list` as its
own live tool call (so its output stays visible) and pipes the JSON into
this script's stdin:

  herdr agent list | uv run --script check-agent-name.py --name <candidate>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")


def live_names(agent_list_payload: dict[str, Any]) -> set[str]:
    try:
        agents = agent_list_payload["result"]["agents"]
    except KeyError as exc:
        raise ValueError(f"unexpected 'herdr agent list' shape -- missing {exc}") from exc
    return {a["name"] for a in agents if "name" in a}


def check(name: str, agent_list_payload: dict[str, Any]) -> None:
    if not NAME_PATTERN.match(name):
        raise ValueError(f"{name!r} does not match ^[A-Za-z][A-Za-z0-9_-]{{0,31}}$")
    taken = live_names(agent_list_payload)
    if name in taken:
        raise ValueError(f"{name!r} is already in use by a live agent")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help="candidate worker-agent name")
    args = parser.parse_args()

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(
            f"error: stdin was not valid JSON -- pipe 'herdr agent list' output into this script ({exc})",
            file=sys.stderr,
        )
        return 1

    try:
        check(args.name, payload)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"name": args.name, "valid": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
