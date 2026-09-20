#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Register this orchestrator's scope, or read the directory of orchestrators."""

from __future__ import annotations

import argparse
import json
import sys

from straw_boss.orchestrator import directory, live_agents, register, release_role


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scope", help="one line naming this orchestrator's main work")
    group.add_argument(
        "--list",
        action="store_true",
        help="read the directory without registering",
    )
    group.add_argument(
        "--release-role",
        action="store_true",
        help="drop whatever named role this session's own record currently holds, without touching its scope",
    )
    parser.add_argument(
        "--role",
        default=None,
        help="claim a named exclusive coordination role (e.g. boss-assistant) alongside --scope; "
        "revokes it from any other record that currently holds it, live or not",
    )
    args = parser.parse_args()
    if args.role is not None and args.scope is None:
        parser.error("--role requires --scope")
    try:
        if args.list:
            result = {"directory": directory(live_agents())}
        elif args.release_role:
            result = release_role()
        else:
            result = register(args.scope, args.role)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
