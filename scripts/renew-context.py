#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Persist this session's continuity record and schedule its own clear.

Run by the session when context-renewal-guard.py asks. The continuity payload
arrives on stdin. Inside Herdr a detached deliver-renewal.py clears this pane
once the turn ends; outside Herdr the notice asks the user to run the clear.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from straw_boss.renewal import (
    CLEAR_COMMAND,
    ROLES,
    record_key,
    record_path,
    write_record,
)


SCRIPTS = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-kind", required=True, choices=("claude", "codex", "agy"))
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--role", required=True, choices=ROLES)
    parser.add_argument("--instruction-path", action="append", default=[])
    args = parser.parse_args()

    pane_id = os.environ.get("HERDR_PANE_ID")
    path = record_path(record_key(pane_id, os.getcwd(), args.agent_kind))
    try:
        record = write_record(
            path,
            pane_id=pane_id,
            agent_kind=args.agent_kind,
            session_id=args.session_id,
            role=args.role,
            payload=sys.stdin.read(),
            instruction_paths=args.instruction_path,
        )
        if args.role == "dispatched-worker":
            for instruction in record["instruction_paths"]:
                subprocess.run(
                    [sys.executable, str(SCRIPTS / "report-progress.py"),
                     "--instruction-path", instruction,
                     "--note", f"Context renewal checkpoint: {path}"],
                    check=True, capture_output=True, text=True,
                )
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if pane_id:
        subprocess.Popen(
            [sys.executable, str(SCRIPTS / "deliver-renewal.py"), "--pane-id", pane_id],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"Context renewal: record {path}; this pane clears after the turn ends.")
    else:
        print(f"Context renewal: record {path}; run {CLEAR_COMMAND} to continue from it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
