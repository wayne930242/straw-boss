#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Take over dispatches another main agent coordinates, at the user's request.

The user decides a takeover; this command never infers one and checks no
liveness. It moves each listed dispatch's main route to the main agent running
it, proven from its own pane, and reports whether a live agent still carries
the previous coordinator identity so that coordinator can be told what moved.
Every listed dispatch is checked before any is written; one refusal writes
nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from straw_boss.dispatch.transfer import caller_route, move_main_routes
from straw_boss.herdr.session import agent_matches_identity
from straw_boss.orchestrator import live_agents


def previous_coordinator_live(route: dict[str, object], agents: list[dict[str, object]]) -> bool:
    kind = "agy" if route["kind"] == "antigravity" else str(route["kind"])
    return any(
        agent_matches_identity(agent, kind, route["session_id"], route["herdr_terminal_id"])
        for agent in agents
    )


def take_over(paths: list[str]) -> dict[str, object]:
    route = caller_route()
    result = move_main_routes(
        [(Path(path), None) for path in paths],
        route,
        reason="user-requested-takeover",
        evidence={"user_requested": True},
    )
    agents = live_agents()
    return {
        "coordinator": route,
        "taken_over": [
            {**entry, "previous_coordinator_live": previous_coordinator_live(entry["before"], agents)}
            for entry in result["moved"]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-requested",
        action="store_true",
        help="the user asked this main agent to take these dispatches over",
    )
    parser.add_argument("--instruction-path", action="append", required=True)
    args = parser.parse_args()
    if not args.user_requested:
        print("error: a takeover runs only when the user asks for it; pass --user-requested", file=sys.stderr)
        return 1
    try:
        result = take_over(args.instruction_path)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
