#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Resolve a dispatched agent's `awaiting-main-agent` checkpoint: deliver
the main agent's reply and record the resolution, atomically.

See skills/dispatching-work/references/plan-mechanics.md's "Main-agent-
action checkpoints". Only targets `mode: herdr-pane`; herdr provides the
provider-neutral live addressing used for both supported agent kinds.

It sends a short delta plus optional references through the shared
session-validating transport, then confirms the text reached the transcript via a short herdr read poll and retries once if a full
poll window never finds it. `status` stays `awaiting-main-agent` after a
successful reply -- only `resolved_by_main_agent_at`/`main_agent_reply`
are added; the worker's own next terminal write closes it out.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dispatch_state import dump_json, load_json, resolve_instruction_status_path
from dispatch_transport import (
    HerdrCommandError,
    confirm_transcript_contains,
    normalize_references,
    send_instruction_message,
)


def reply_to_worker(
    worker_instruction_path: str,
    reply: str,
    references: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    inst_path = Path(worker_instruction_path)
    if not inst_path.is_file():
        raise ValueError(f"no worker instruction file at {inst_path}")
    instruction = load_json(inst_path)

    mode = instruction.get("mode")
    agent_kind = instruction.get("agent_kind")
    if mode != "herdr-pane" or agent_kind not in ("claude", "codex"):
        raise ValueError(
            f"worker {inst_path} is mode={mode!r} agent_kind={agent_kind!r} -- "
            "awaiting-main-agent requires a herdr-pane worker using a supported agent kind"
        )

    herdr_pane_id = instruction.get("herdr_pane_id")
    if not herdr_pane_id:
        raise ValueError(f"worker {inst_path} has no herdr_pane_id recorded -- was dispatch confirmed?")

    status_path = resolve_instruction_status_path(inst_path, instruction)
    if not status_path.is_file():
        raise ValueError(f"no status file at {status_path} -- worker has not reported awaiting-main-agent")
    status_payload = load_json(status_path)
    if status_payload.get("status") != "awaiting-main-agent":
        raise ValueError(
            f"status file {status_path} reports status={status_payload.get('status')!r}, "
            f"not 'awaiting-main-agent' -- refusing to reply to a checkpoint that isn't open"
        )

    normalized_references = normalize_references(references)
    # A genuine herdr failure other than a confirmed non-start -- any
    # HerdrCommandError whose code isn't agent_prompt_stalled, including an
    # ambiguous timeout -- propagates immediately and never triggers a
    # resend. Only a stall herdr itself confirmed, or a poll window that
    # completes without ever finding the reply, retries below.
    try:
        send_instruction_message(
            inst_path, "worker", "reply", reply, references=normalized_references
        )
        delivered = confirm_transcript_contains(herdr_pane_id, reply, str(agent_kind))
    except HerdrCommandError as exc:
        if exc.error_code != "agent_prompt_stalled":
            raise
        delivered = False
    if not delivered:
        send_instruction_message(
            inst_path,
            "worker",
            "reply-retry",
            reply,
            references=normalized_references,
        )
        if not confirm_transcript_contains(herdr_pane_id, reply, str(agent_kind)):
            raise ValueError(
                f"sent the reply to pane {herdr_pane_id!r} via herdr (that call itself succeeded) but could not "
                f"confirm it landed in the transcript after one retry -- likely still queued in a "
                f"busy pane rather than lost, but not certain either way. status file left untouched "
                f"at {status_path}; inspect the pane through the dispatch tooling before resending "
            )

    status_payload["resolved_by_main_agent_at"] = datetime.now(timezone.utc).isoformat()
    status_payload["main_agent_reply"] = reply
    if normalized_references:
        status_payload["main_agent_reply_refs"] = list(normalized_references)
    dump_json(status_path, status_payload)

    return {"resolved": True, "status_path": str(status_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worker-instruction-path",
        required=True,
        help="path to the blocked worker's own dispatch instruction file",
    )
    parser.add_argument("--reply", required=True, help="the reply text to deliver into the worker's pane")
    parser.add_argument("--ref", action="append", default=[], help="instruction/context reference")
    args = parser.parse_args()

    try:
        result = reply_to_worker(args.worker_instruction_path, args.reply, args.ref)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
