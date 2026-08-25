#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Send a cross-session dispatch message without exposing receiver addresses."""

from __future__ import annotations

import argparse
import json
import sys

from dispatch_transport import send_instruction_message


INTENTS = ("question", "inform", "reply", "redirect", "cancel", "status", "control")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruction-path", required=True)
    parser.add_argument("--to", required=True, choices=("main", "worker"))
    parser.add_argument("--intent", required=True, choices=INTENTS)
    parser.add_argument("--message", required=True)
    args = parser.parse_args()
    try:
        endpoint = send_instruction_message(
            args.instruction_path, args.to, args.intent, args.message
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "submitted": True,
                "target": endpoint.target,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
