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

It sends through the shared session-validating transport, then confirms the
text reached the transcript via a short herdr read poll and retries once if a full
poll window never finds it. `status` stays `awaiting-main-agent` after a
successful reply -- only `resolved_by_main_agent_at`/`main_agent_reply`
are added; the worker's own next terminal write closes it out.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dispatch_state import dump_json, load_json, resolve_instruction_status_path
from dispatch_transport import run_herdr_raw, send_instruction_message

# A generous tail: once the resumed worker starts producing real output, a
# small window scrolls the reply text itself out of view within seconds,
# turning "confirmed delivered" into a false "not found" -- retrying then
# double-sends into a pane that's actively executing the first send.
CONFIRM_READ_LINES = 500
CONFIRM_POLL_ATTEMPTS = 6
CONFIRM_POLL_INTERVAL_S = 2


def read_transcript(target: str, agent_kind: str) -> str:
    # `agent read` (confirmed live) has no JSON output mode at all --
    # `--format` is only `text`/`ansi` -- its stdout *is* the transcript.
    args = ["agent", "read", target, "--lines", str(CONFIRM_READ_LINES)]
    if agent_kind == "codex":
        # Confirmed live: herdr's default `recent` source can be empty for a
        # Codex pane even though its visible screen contains the prompt.
        return run_herdr_raw([*args, "--source", "visible"])
    try:
        return run_herdr_raw(args)
    except ValueError as exc:
        # Reported live (a peer session hit this exact error): herdr refuses
        # to scroll a pane's alternate-screen scrollback while its agent is
        # still `working` ("...can only be captured by scrolling while idle.
        # Wait and retry, or use --source visible") -- the visible screen can
        # still be read in that state. Detected via herdr's own suggestion
        # text in its error message, not a hardcoded status check, so this
        # doesn't need to track herdr's exact wording for "not idle" itself.
        if "--source visible" not in str(exc):
            raise
        return run_herdr_raw([*args, "--source", "visible"])


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def reply_landed(transcript: str, reply: str) -> bool:
    # Presence only -- not "content follows it". The worker may take a
    # while to visibly respond once it starts real work; requiring
    # trailing content would make this indistinguishable from "not sent
    # yet" and force a resend into a pane that already received it. This
    # only confirms the text reached the pane, not that the worker has
    # acted on it -- distinguishing those isn't this script's job.
    #
    # Whitespace-normalized: confirmed live that a real pane hard-wraps a
    # long reply at its column width, turning the space before the wrap
    # point into a newline -- an exact match against the original text
    # then fails even though the reply landed, triggering a real duplicate
    # send (confirmed live too: the worker executed the same reply twice).
    return normalize_whitespace(transcript).find(normalize_whitespace(reply)) >= 0


def confirm_landed(target: str, reply: str, agent_kind: str) -> bool:
    for attempt in range(CONFIRM_POLL_ATTEMPTS):
        if reply_landed(read_transcript(target, agent_kind), reply):
            return True
        if attempt < CONFIRM_POLL_ATTEMPTS - 1:
            time.sleep(CONFIRM_POLL_INTERVAL_S)
    return False


def reply_to_worker(worker_instruction_path: str, reply: str) -> dict[str, Any]:
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

    endpoint = send_instruction_message(inst_path, "worker", "reply", reply)
    # A genuine herdr failure (timeout, pane gone) propagates immediately
    # and never triggers a resend -- only a poll window that completes
    # without ever finding the reply retries below.
    if not confirm_landed(endpoint.pane_id, reply, str(agent_kind)):
        send_instruction_message(inst_path, "worker", "reply-retry", reply)
        if not confirm_landed(endpoint.pane_id, reply, str(agent_kind)):
            raise ValueError(
                f"sent the reply to pane {endpoint.pane_id!r} via herdr (that call itself succeeded) but could not "
                f"confirm it landed in the transcript after one retry -- likely still queued in a "
                f"busy pane rather than lost, but not certain either way. status file left untouched "
                f"at {status_path}; inspect the pane through the dispatch tooling before resending "
            )

    status_payload["resolved_by_main_agent_at"] = datetime.now(timezone.utc).isoformat()
    status_payload["main_agent_reply"] = reply
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
    args = parser.parse_args()

    try:
        result = reply_to_worker(args.worker_instruction_path, args.reply)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
