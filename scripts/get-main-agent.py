#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Reads a dispatch instruction's main-agent reachability fields back.

A dispatch instruction (<home>/.straw-boss/dispatch/<app>--<slug>.json,
written by dispatch-task.py write -- see
skills/dispatching-work/references/dispatch-mechanics.md) records its
main agent's own herdr pane id and SendMessage peer name as structured
fields. A dispatched agent calls this script to read them back at report
time, instead of relying on its own recollection of the prose stated in
its dispatch prompt -- a long-running or /compact-ed task's context may
no longer reliably retain a value stated once, early, in that prompt.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def get_main_agent(instruction_path: Path) -> dict[str, Any]:
    if not instruction_path.is_file():
        raise ValueError(f"no instruction file at {instruction_path}")
    payload = load_json(instruction_path)
    pane_id = payload.get("main_agent_herdr_pane_id")
    peer = payload.get("main_agent_send_message_peer")
    if pane_id is None and peer is None:
        raise ValueError(
            f"instruction file {instruction_path} has no main-agent reachability recorded -- "
            f"it may predate this field; fall back to whatever your dispatch prompt's prose states"
        )
    return {"main_agent_herdr_pane_id": pane_id, "main_agent_send_message_peer": peer}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instruction-path", required=True, help="path to this dispatch's own instruction file")
    args = parser.parse_args()

    try:
        result = get_main_agent(Path(args.instruction_path))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
