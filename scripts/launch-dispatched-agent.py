#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Start and prompt a herdr dispatched agent with its mandatory contract."""

from __future__ import annotations

import argparse
import json
import sys

from straw_boss.dispatch.launch import launch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruction-path", required=True)
    parser.add_argument(
        "--name",
        default=None,
        help="operator-visible herdr agent name; omit for one derived automatically "
        "from the instruction's app and role",
    )
    parser.add_argument(
        "--agent-arg",
        action="append",
        default=[],
        help="additional provider argument; repeat once per argument",
    )
    args = parser.parse_args()
    try:
        result = launch(args.instruction_path, args.name, args.agent_arg)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
