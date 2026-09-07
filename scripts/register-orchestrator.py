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

from orchestrator_registry import directory, live_agents, register


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scope", help="one line naming this orchestrator's main work")
    group.add_argument(
        "--list",
        action="store_true",
        help="read the directory without registering",
    )
    args = parser.parse_args()
    try:
        result = (
            {"directory": directory(live_agents())}
            if args.list
            else register(args.scope)
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
