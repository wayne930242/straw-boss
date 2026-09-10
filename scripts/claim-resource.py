#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Cross-main-agent mutual exclusion for a shared external resource -- a port
that can't be parameterized, or a database migrations are verified
against -- something a git worktree cannot isolate because it lives
outside any one checkout. See
skills/dispatching-work/references/shared-resource-coordination.md.

Lock files live at <home>/.straw-boss/locks/<resource>.json, one per
resource identity, independent of any single main agent's own dispatch state --
this is the one piece of straw-boss state genuinely shared and contended
across multiple concurrent main-agent sessions, not just within one main
agent's own fleet.

  acquire    -- atomically create the lock if free. If held and not yet
                expired (age has not yet reached the current holder's own
                ttl_seconds), reports it held without waiting. One-shot --
                use `wait`
                below for the common case of actually wanting to wait.
  wait       -- block until the resource is free, then acquire it.
                Loops `acquire` internally with the poll cadence it
                reports, printing progress to stderr. By default never
                gives up before the currently observed holder's own
                ttl_seconds would make it reclaimable -- a resource
                genuinely cannot stay contended forever as long as
                something eventually calls this. --max-wait-seconds is
                an optional, deliberate early cutoff for a caller that
                wants to fail fast instead.
  claim-port -- for a task whose dev-server port is configurable: derive
                a starting candidate deterministically from --key, then
                acquire it, incrementing on contention up to
                --max-attempts. Never blocks -- a flexible port that's
                taken just tries the next number, it doesn't queue.
  release    -- remove the lock. Refuses if --holder doesn't match the
                recorded holder, unless --force is given.
  status     -- read-only, reports whether it's held and by whom.
  list       -- read-only, reports every current lock (optionally
                filtered by a resource-id prefix, e.g. "port--") -- this
                is also the live record of which port/DB lock is
                currently assigned to which worker.
  gc         -- read-write, deletes every lock file already past its own
                ttl_seconds, regardless of whether anyone is currently
                contending for it. Not required for correctness (the
                reactive reclaim inside `acquire` already handles that
                the moment anyone asks again) -- purely housekeeping, so
                `list` doesn't accumulate long-dead entries from tasks
                that crashed and nothing ever re-contended for.

`wait` and `claim-port` block/sleep internally, unlike the bare `acquire`
primitive they're built on. This is deliberate here, unlike this plugin's
main-agent-level background status watcher (see plan-mechanics.md), which
stay external because the main agent needs to remain responsive and observable
while watching several tasks at once. A single dispatched task waiting on
one resource has no such audience -- nothing outside it needs turn-by-
turn visibility into its own wait, so folding the loop into one blocking
command is simpler and removes an entire class of hand-rolled-bash bugs
(JSON parsing, integer-vs-float arithmetic, zsh quirks) that a dispatch
instruction would otherwise have to get right verbatim.

For a `port--<app>--<port-number>` resource, `acquire` also probes the
actual OS-level port before ever touching the lock file -- this is a
cooperative lock, and nothing stops a process outside this script from
already sitting on that port. This is best-effort, not a guarantee: it's
IPv4 only, and there's an unavoidable gap between the probe and whenever
the caller actually binds for real a moment later. A dispatch instruction
that starts a dev server still needs to handle an actual bind failure as
a real possibility despite a successful claim, not assume the claim alone
proves the port usable.
"""

from __future__ import annotations

import argparse
import json
import sys

from straw_boss.resource_lock import (
    acquire,
    claim_port,
    gc,
    list_locks,
    release,
    status,
    wait_for,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)

    acquire_p = sub.add_parser("acquire", help="claim the resource if free")
    acquire_p.add_argument(
        "--resource", required=True, help="stable identity, e.g. db-migration--waydosoft01-staging or port--api--5000"
    )
    acquire_p.add_argument(
        "--holder", required=True, help="who's claiming it, e.g. <app>--<slug> matching the dispatch instruction filename"
    )
    acquire_p.add_argument(
        "--ttl-seconds", type=int, default=1800, help="how long before an unreleased lock is treated as abandoned"
    )
    acquire_p.add_argument("--note", default=None)
    acquire_p.add_argument(
        "--requester-instruction-path",
        default=None,
        help="the exact dispatch instruction path; coordination resolves both main agents through instruction-keyed scripts",
    )

    wait_p = sub.add_parser("wait", help="block until the resource is free, then acquire it")
    wait_p.add_argument("--resource", required=True)
    wait_p.add_argument("--holder", required=True)
    wait_p.add_argument("--ttl-seconds", type=int, default=1800)
    wait_p.add_argument("--note", default=None)
    wait_p.add_argument("--requester-instruction-path", default=None)
    wait_p.add_argument(
        "--max-wait-seconds",
        type=int,
        default=None,
        help=(
            "explicit early cutoff, exits nonzero once reached. Default (unset) waits up to 3x the largest "
            "ttl_seconds observed among holders seen so far -- comfortably covers one legitimately slow holder "
            "while still terminating under churn. Pass this only to deliberately fail faster and let a human "
            "decide sooner"
        ),
    )

    claim_port_p = sub.add_parser("claim-port", help="derive a port deterministically and acquire it, retrying on contention")
    claim_port_p.add_argument("--app", required=True)
    claim_port_p.add_argument("--key", required=True, help="stable string to derive the starting candidate from, e.g. the worktree's absolute path")
    claim_port_p.add_argument("--base", type=int, default=3000)
    claim_port_p.add_argument("--range", type=int, default=500, dest="port_range")
    claim_port_p.add_argument("--max-attempts", type=int, default=5)
    claim_port_p.add_argument("--holder", required=True)
    claim_port_p.add_argument("--ttl-seconds", type=int, default=1800)
    claim_port_p.add_argument("--note", default=None)
    claim_port_p.add_argument("--requester-instruction-path", default=None)

    release_p = sub.add_parser("release", help="free the resource")
    release_p.add_argument("--resource", required=True)
    release_p.add_argument("--holder", required=True)
    release_p.add_argument("--force", action="store_true", help="release even if --holder doesn't match the recorded holder")

    status_p = sub.add_parser("status", help="read-only check")
    status_p.add_argument("--resource", required=True)

    list_p = sub.add_parser("list", help="list current locks, optionally filtered by a resource-id prefix")
    list_p.add_argument("--prefix", default=None, help="only resources whose id starts with this, e.g. 'port--'")

    sub.add_parser("gc", help="delete every lock already past its own ttl_seconds, whether or not anyone is waiting on it")

    args = parser.parse_args()

    try:
        if args.action == "acquire":
            result = acquire(args.resource, args.holder, args.ttl_seconds, args.note, args.requester_instruction_path)
        elif args.action == "wait":
            result = wait_for(
                args.resource, args.holder, args.ttl_seconds, args.note, args.requester_instruction_path, args.max_wait_seconds
            )
        elif args.action == "claim-port":
            result = claim_port(
                args.app,
                args.key,
                args.base,
                args.port_range,
                args.max_attempts,
                args.holder,
                args.ttl_seconds,
                args.note,
                args.requester_instruction_path,
            )
        elif args.action == "release":
            result = release(args.resource, args.holder, args.force)
        elif args.action == "status":
            result = status(args.resource)
        elif args.action == "list":
            result = list_locks(args.prefix)
        else:
            result = gc()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
