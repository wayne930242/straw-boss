#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Emit one JSON event for every persisted Plan status transition.

Unlike the old shell polling loop, this watcher deduplicates by complete file
content rather than filename. A checkpoint file that is later overwritten with
``done`` or ``failed`` therefore emits again. A fresh watcher intentionally
starts with no remembered revisions and emits every current status once, so a
resumed main-agent session can recover from durable Plan state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


VALID_STATUSES = {
    "done",
    "failed",
    "awaiting-authorization",
    "awaiting-user-input",
    "awaiting-main-agent",
    "cancelled",
}


def status_dir(plan_slug: str) -> Path:
    return Path.home() / ".straw-boss" / "plans" / plan_slug / "status"


def collect_status_changes(plan_slug: str, seen_revisions: dict[str, str]) -> list[dict[str, Any]]:
    directory = status_dir(plan_slug)
    if not directory.is_dir():
        raise ValueError(f"status directory {directory} does not exist -- unknown plan {plan_slug!r}")

    events: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            raw = path.read_bytes()
            payload = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            # A writer may have been observed between truncate and replace on
            # an older status file. Do not remember the broken revision; the
            # next scan will retry it.
            continue

        if not isinstance(payload, dict) or payload.get("status") not in VALID_STATUSES:
            continue

        revision = hashlib.sha256(raw).hexdigest()
        key = str(path)
        if seen_revisions.get(key) == revision:
            continue
        seen_revisions[key] = revision
        events.append({**payload, "task_id": path.stem, "revision": revision})
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="plan slug")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="seconds between scans (default: 1.0)",
    )
    parser.add_argument("--once", action="store_true", help="scan once and exit")
    args = parser.parse_args()
    if args.poll_interval <= 0:
        print("error: --poll-interval must be greater than zero", file=sys.stderr)
        return 1

    seen_revisions: dict[str, str] = {}
    while True:
        try:
            events = collect_status_changes(args.plan, seen_revisions)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        for event in events:
            print(json.dumps(event), flush=True)
        if args.once:
            return 0
        time.sleep(args.poll_interval)


if __name__ == "__main__":
    raise SystemExit(main())
