#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Appends a timestamped progress note to a dispatch's own progress log.

Callable by a dispatched agent at any point during its work, any number
of times -- not just at a terminal state or checkpoint. Writes to a
sibling append-only log next to the dispatch's own instruction file
(<home>/.straw-boss/dispatch/<app>--<slug>.json ->
<app>--<slug>.progress.jsonl), never to the instruction file itself.

Deliberately a separate file from any status file a Monitor loop
watches: plan-mechanics.md's Monitor dedups strictly by filename, so an
intermediate write to a status file's own filename would be treated as
"already seen," silently swallowing a later genuine terminal write to
that same filename. This script never touches a status file.

This is a log, not a notification -- it never sends a SendMessage push.
See skills/notifying-main-agent/SKILL.md's "Branch: Report your own
status" for the terminal-state/checkpoint push, which is separate.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def progress_log_path(instruction_path: Path) -> Path:
    stem = instruction_path.name.removesuffix(".json")
    return instruction_path.with_name(f"{stem}.progress.jsonl")


def append_progress(instruction_path: Path, note: str) -> Path:
    if not instruction_path.is_file():
        raise ValueError(f"no instruction file at {instruction_path}")
    log_path = progress_log_path(instruction_path)
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "note": note}
    with log_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return log_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruction-path", required=True, help="path to this dispatch's own instruction file")
    parser.add_argument("--note", required=True, help="free-text progress note")
    args = parser.parse_args()

    try:
        path = append_progress(Path(args.instruction_path), args.note)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"appended to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
