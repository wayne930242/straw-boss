#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Send one factual delta to another registered orchestrator."""

from __future__ import annotations

import argparse
import json
import sys
import uuid

from straw_boss.herdr.transport import EndpointUnavailableError
from straw_boss.orchestrator import ORCHESTRATOR_INTENTS, send


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", required=True, help="registered name, or its herdr pane id")
    parser.add_argument("--intent", required=True, choices=ORCHESTRATOR_INTENTS)
    parser.add_argument("--in-reply-to", help="the question id an answer replies to")
    parser.add_argument("--message", required=True, help="one delta, at most two sentences")
    parser.add_argument("--ref", action="append", default=[], help="source/artifact reference")
    args = parser.parse_args()
    message_id = str(uuid.uuid4())
    try:
        result = send(
            to=args.to,
            intent=args.intent,
            message=args.message,
            message_id=message_id,
            in_reply_to=args.in_reply_to,
            references=args.ref,
        )
    except EndpointUnavailableError as exc:
        # The other orchestrator is gone. Its body is already in the delivery
        # ledger, so report non-delivery and let this session carry on.
        print(f"warning: {exc}", file=sys.stderr)
        print(
            json.dumps(
                {"submitted": False, "recorded": True, "message_id": message_id},
                indent=2,
            )
        )
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
