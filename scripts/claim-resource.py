#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Cross-boss mutual exclusion for a shared external resource -- a port
that can't be parameterized, or a database migrations are verified
against -- something a git worktree cannot isolate because it lives
outside any one checkout. See
skills/dispatching-work/references/shared-resource-coordination.md.

Lock files live at <home>/.straw-boss/locks/<resource>.json, one per
resource identity, independent of any single boss's own dispatch state --
this is the one piece of straw-boss state genuinely shared and contended
across multiple concurrent boss sessions, not just within one boss's own
fleet.

  acquire    -- atomically create the lock if free. If held and not
                expired (age > the current holder's own ttl_seconds),
                reports it held without waiting. One-shot -- use `wait`
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

`wait` and `claim-port` block/sleep internally, unlike the bare `acquire`
primitive they're built on. This is deliberate here, unlike this plugin's
boss-level Monitor-based polling loops (see plan-mechanics.md), which
stay external because the boss needs to remain responsive and observable
while watching several tasks at once. A single dispatched task waiting on
one resource has no such audience -- nothing outside it needs turn-by-
turn visibility into its own wait, so folding the loop into one blocking
command is simpler and removes an entire class of hand-rolled-bash bugs
(JSON parsing, integer-vs-float arithmetic, zsh quirks) that a dispatch
instruction would otherwise have to get right verbatim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESOURCE_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def mp_dev_root() -> Path:
    return Path.home() / ".straw-boss"


def lock_path(resource: str) -> Path:
    if not RESOURCE_RE.match(resource):
        raise ValueError(
            f"--resource {resource!r} has characters outside [A-Za-z0-9._-] -- it becomes a filename "
            f"(and must stay portable to Windows), use '--' as a separator instead, e.g. "
            f"'db-migration--waydosoft01-staging' or 'port--api--5000'"
        )
    return mp_dev_root() / "locks" / f"{resource}.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def age_seconds(acquired_at: str) -> float:
    acquired = datetime.fromisoformat(acquired_at)
    return (datetime.now(timezone.utc) - acquired).total_seconds()


def acquire(resource: str, holder: str, ttl_seconds: int, note: str | None, holder_boss: str | None) -> dict[str, Any]:
    path = lock_path(resource)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "resource": resource,
        "holder": holder,
        "holder_boss": holder_boss,
        "note": note,
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": ttl_seconds,
    }

    for attempt in range(2):  # second pass only after reclaiming a stale lock
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            existing = load_json(path)
            age = age_seconds(existing["acquired_at"])
            remaining = existing["ttl_seconds"] - age
            if remaining > 0:
                # A poll cadence, not "time left on the holder's TTL" -- most holders
                # release long before their TTL expires, so waiting out the full
                # remaining time would badly oversleep a fast-finishing holder.
                return {
                    "acquired": False,
                    "resource": resource,
                    "held_by": existing["holder"],
                    "held_by_boss": existing.get("holder_boss"),
                    "held_note": existing.get("note"),
                    "age_seconds": round(age, 1),
                    "held_ttl_seconds": existing["ttl_seconds"],
                    "retry_after_seconds": max(5, min(30, int(remaining))),
                }
            # Stale -- the previous holder never released and outlived its own ttl.
            path.unlink()
            continue
        else:
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(payload, indent=2) + "\n")
            return {"acquired": True, "resource": resource, "holder": holder, "reclaimed_stale": attempt > 0}

    raise ValueError(
        f"could not acquire lock on {resource!r} -- contended again immediately after reclaiming a stale entry, try again"
    )


WAIT_CHURN_MULTIPLIER = 3  # see wait_for's docstring note below


def wait_for(
    resource: str, holder: str, ttl_seconds: int, note: str | None, holder_boss: str | None, max_wait_seconds: int | None
) -> dict[str, Any]:
    """A resource can go unavailable for two different reasons, and the give-up
    deadline has to handle both without an explicit --max-wait-seconds:

    - One holder, legitimately slow: never give up before *that holder's own*
      ttl_seconds would make it reclaimable -- otherwise this fails a task that
      would have succeeded on the very next poll.
    - Several holders in a row (churn): a naive per-holder deadline that resets
      on every new holder never terminates. max_ttl_seen only grows when a
      materially larger ttl is actually observed, so capping total elapsed at
      WAIT_CHURN_MULTIPLIER times the largest ttl seen so far still comfortably
      covers any single legitimate holder while guaranteeing termination under
      churn.
    """
    started = time.monotonic()
    max_ttl_seen = 0
    while True:
        result = acquire(resource, holder, ttl_seconds, note, holder_boss)
        if result["acquired"]:
            return result
        retry = result["retry_after_seconds"]
        elapsed = time.monotonic() - started
        max_ttl_seen = max(max_ttl_seen, result["held_ttl_seconds"])
        reclaimable_in = max(0.0, result["held_ttl_seconds"] - result["age_seconds"])
        deadline = max_ttl_seen * WAIT_CHURN_MULTIPLIER
        if max_wait_seconds is not None:
            deadline = min(deadline, max_wait_seconds)
        boss_bit = f" (boss {result['held_by_boss']!r})" if result.get("held_by_boss") else ""
        print(
            f"waiting on {resource!r}, held by {result['held_by']!r}{boss_bit}, retrying in {retry}s "
            f"({elapsed:.0f}s elapsed of {deadline:.0f}s budget; this holder's own ttl reclaimable in "
            f"~{reclaimable_in:.0f}s if not released sooner)",
            file=sys.stderr,
        )
        if elapsed > deadline:
            reason = (
                f"--max-wait-seconds {max_wait_seconds} reached"
                if max_wait_seconds is not None
                else f"{WAIT_CHURN_MULTIPLIER}x the largest ttl_seconds observed ({max_ttl_seen}s) reached -- "
                f"likely several different holders in a row rather than one slow one"
            )
            raise ValueError(f"gave up waiting on {resource!r} after {elapsed:.0f}s -- still held by {result['held_by']!r} ({reason})")
        time.sleep(retry)


def claim_port(
    app: str,
    key: str,
    base: int,
    port_range: int,
    max_attempts: int,
    holder: str,
    ttl_seconds: int,
    note: str | None,
    holder_boss: str | None,
) -> dict[str, Any]:
    start = base + int(hashlib.sha256(key.encode()).hexdigest(), 16) % port_range
    candidate = start
    last_result: dict[str, Any] | None = None
    for _ in range(max_attempts):
        resource = f"port--{app}--{candidate}"
        result = acquire(resource, holder, ttl_seconds, note, holder_boss)
        if result["acquired"]:
            result["port"] = candidate
            return result
        last_result = result
        candidate += 1
    raise ValueError(
        f"could not claim a free port for {app!r} after {max_attempts} attempts starting from {start} -- "
        f"last contended: {last_result}"
    )


def release(resource: str, holder: str, force: bool) -> dict[str, Any]:
    path = lock_path(resource)
    if not path.is_file():
        raise ValueError(f"no lock held on {resource!r} -- nothing to release")
    existing = load_json(path)
    if existing["holder"] != holder and not force:
        raise ValueError(
            f"lock on {resource!r} is held by {existing['holder']!r}, not {holder!r} -- "
            f"refusing to release someone else's lock without --force"
        )
    path.unlink()
    return {"released": True, "resource": resource, "was_held_by": existing["holder"]}


def status(resource: str) -> dict[str, Any]:
    path = lock_path(resource)
    if not path.is_file():
        return {"held": False, "resource": resource}
    existing = load_json(path)
    age = age_seconds(existing["acquired_at"])
    return {
        "held": True,
        "resource": resource,
        "holder": existing["holder"],
        "holder_boss": existing.get("holder_boss"),
        "note": existing.get("note"),
        "age_seconds": round(age, 1),
        "expired": age > existing["ttl_seconds"],
    }


def list_locks(prefix: str | None) -> dict[str, Any]:
    locks_dir = mp_dev_root() / "locks"
    if not locks_dir.is_dir():
        return {"locks": []}
    entries = []
    for path in sorted(locks_dir.glob("*.json")):
        resource = path.stem
        if prefix is not None and not resource.startswith(prefix):
            continue
        existing = load_json(path)
        age = age_seconds(existing["acquired_at"])
        entries.append(
            {
                "resource": resource,
                "holder": existing["holder"],
                "holder_boss": existing.get("holder_boss"),
                "note": existing.get("note"),
                "age_seconds": round(age, 1),
                "expired": age > existing["ttl_seconds"],
            }
        )
    return {"locks": entries}


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
        "--requester-boss",
        default=None,
        help="the dispatching boss's own herdr pane id or SendMessage peer name -- lets a stuck waiter's boss reach out directly instead of guessing",
    )

    wait_p = sub.add_parser("wait", help="block until the resource is free, then acquire it")
    wait_p.add_argument("--resource", required=True)
    wait_p.add_argument("--holder", required=True)
    wait_p.add_argument("--ttl-seconds", type=int, default=1800)
    wait_p.add_argument("--note", default=None)
    wait_p.add_argument("--requester-boss", default=None)
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
    claim_port_p.add_argument("--requester-boss", default=None)

    release_p = sub.add_parser("release", help="free the resource")
    release_p.add_argument("--resource", required=True)
    release_p.add_argument("--holder", required=True)
    release_p.add_argument("--force", action="store_true", help="release even if --holder doesn't match the recorded holder")

    status_p = sub.add_parser("status", help="read-only check")
    status_p.add_argument("--resource", required=True)

    list_p = sub.add_parser("list", help="list current locks, optionally filtered by a resource-id prefix")
    list_p.add_argument("--prefix", default=None, help="only resources whose id starts with this, e.g. 'port--'")

    args = parser.parse_args()

    try:
        if args.action == "acquire":
            result = acquire(args.resource, args.holder, args.ttl_seconds, args.note, args.requester_boss)
        elif args.action == "wait":
            result = wait_for(
                args.resource, args.holder, args.ttl_seconds, args.note, args.requester_boss, args.max_wait_seconds
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
                args.requester_boss,
            )
        elif args.action == "release":
            result = release(args.resource, args.holder, args.force)
        elif args.action == "status":
            result = status(args.resource)
        else:
            result = list_locks(args.prefix)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
