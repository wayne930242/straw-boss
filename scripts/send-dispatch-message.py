#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Send a short cross-session delta with optional structured references."""

from __future__ import annotations

import argparse
import json
import sys
import uuid

from dispatch_transport import send_instruction_message


INTENTS = ("question", "answer", "inform", "reply", "redirect", "control")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruction-path", required=True)
    parser.add_argument("--sender-instruction-path")
    parser.add_argument("--to", required=True, choices=("main", "worker"))
    parser.add_argument("--intent", required=True, choices=INTENTS)
    parser.add_argument("--in-reply-to")
    parser.add_argument("--message", required=True, help="one delta, at most two sentences")
    parser.add_argument("--ref", action="append", default=[], help="source/artifact reference")
    args = parser.parse_args()
    message_id = str(uuid.uuid4())
    try:
        endpoint = send_instruction_message(
            args.instruction_path,
            args.to,
            args.intent,
            args.message,
            sender_instruction_path=args.sender_instruction_path,
            in_reply_to=args.in_reply_to,
            message_id=message_id,
            references=args.ref,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "submitted": True,
                "message_id": message_id,
                "target": endpoint.target,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
