"""File-backed mutual exclusion for a resource no git worktree can isolate.

The operator-facing manual -- what each verb does and why `wait` blocks in
process -- is `claim-resource.py`'s own docstring, because that text is its
`--help` output.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from straw_boss.dispatch.state import load_json, straw_boss_root


RESOURCE_RE = re.compile(r"^[A-Za-z0-9._-]+$")

PORT_RESOURCE_RE = re.compile(r"^port--.+--(\d+)$")

def lock_path(resource: str) -> Path:
    if not RESOURCE_RE.match(resource):
        raise ValueError(
            f"--resource {resource!r} has characters outside [A-Za-z0-9._-] -- it becomes a filename "
            f"(and must stay portable to Windows), use '--' as a separator instead, e.g. "
            f"'db-migration--waydosoft01-staging' or 'port--api--5000'"
        )
    return straw_boss_root() / "locks" / f"{resource}.json"

def port_from_resource(resource: str) -> int | None:
    m = PORT_RESOURCE_RE.match(resource)
    if m is None:
        return None
    port = int(m.group(1))
    if not (0 < port <= 65535):
        raise ValueError(f"--resource {resource!r} names port {port}, outside the valid range 1-65535")
    return port

def port_is_free(port: int) -> bool:
    """Best-effort, IPv4 only. Deliberately no SO_REUSEADDR -- confirmed
    empirically (macOS) that setting it lets a 0.0.0.0 probe and a
    127.0.0.1 occupant (or vice versa) silently coexist, which would
    defeat the point of this check. Binding 0.0.0.0, not 127.0.0.1, is
    what actually catches an occupant regardless of which interface it
    bound -- also confirmed empirically, a 127.0.0.1-only probe misses a
    0.0.0.0-bound occupant. Also catches OverflowError as a defense-in-depth
    belt-and-suspenders -- port_from_resource and claim_port already
    validate the range before this is ever called with something invalid,
    but this function shouldn't crash the caller either way."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        return True
    except (OSError, OverflowError):
        return False
    finally:
        s.close()

RECLAIM_MUTEX_STALE_SECONDS = 10  # generous multiple of the real work's actual duration

def with_reclaim_mutex(resource: str, fn):
    """Serializes 'check staleness, then replace' for one resource behind a
    short-lived mutex file, so that whole sequence runs as one uninterrupted
    critical section instead of racing another concurrent reclaimer through
    it. Runs fn() and returns its result if we won the mutex; returns None
    (never confused with fn() legitimately returning False) if we backed off
    because someone else currently holds it -- the caller treats that as
    ordinary contention and re-observes current state, not a definitive loss.

    Earlier attempts tried to make the reclaim itself lock-free: unlink()-
    then-recreate raced a FileNotFoundError crash and, worse, a silent
    double-grant (deleting a just-created live lock); os.replace()-then-
    read-back-to-verify still let two racers each read back their own write
    and both conclude they won, because write and verify aren't one atomic
    step; os.rename() as the mutex fixed the two-racer case but not a third
    party's independent fresh acquire() landing in the gap and later being
    silently destroyed. All three were reproduced live. A short-lived mutex
    that serializes the whole decision, rather than trying to make the
    decision itself atomic via cleverer primitives, is what actually closes
    every one of those windows -- while the mutex is held, nothing else
    touches this resource's lock file at all, reclaim or otherwise.

    The mutex is itself just an O_CREAT|O_EXCL presence marker with no
    content to protect, so *its* staleness handling doesn't have the same
    problem: if two processes both decide an abandoned mutex should be
    cleared and both unlink() it, at most one of their subsequent
    os.open(O_CREAT|O_EXCL) attempts can still win -- unlike the real lock,
    there's no data to silently destroy by racing its removal."""
    mutex_path = lock_path(resource).with_suffix(".json.reclaim-mutex")
    for _ in range(2):
        try:
            fd = os.open(mutex_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                mtime = mutex_path.stat().st_mtime
            except FileNotFoundError:
                continue  # vanished between our failed open and our stat -- retry
            if time.time() - mtime > RECLAIM_MUTEX_STALE_SECONDS:
                mutex_path.unlink(missing_ok=True)
                continue
            return None  # someone else is actively deciding this resource right now
        else:
            os.close(fd)
            break
    else:
        return None

    try:
        return fn()
    finally:
        mutex_path.unlink(missing_ok=True)

def reclaim_stale(path: Path, payload: dict[str, Any]) -> bool:
    """Only ever runs inside with_reclaim_mutex -- by the time we're here,
    we're the sole process touching this resource's lock file, so a plain
    read-check-replace is safe with no other reclaimer able to interleave."""
    try:
        existing = load_json(path)
    except (FileNotFoundError, json.JSONDecodeError):
        # Gone since we last observed it (released, or reclaimed by whoever
        # held the mutex just before us) -- nothing stale left to reclaim;
        # the caller's own next os.open(O_CREAT|O_EXCL) will see a free path.
        return False
    age = age_seconds(existing["acquired_at"])
    if age <= existing["ttl_seconds"]:
        return False  # no longer stale -- refreshed/recreated before we got the mutex
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{time.monotonic_ns()}")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    os.replace(tmp, path)  # safe here: the mutex guarantees nobody else is touching this path
    return True

def age_seconds(acquired_at: str) -> float:
    acquired = datetime.fromisoformat(acquired_at)
    return (datetime.now(timezone.utc) - acquired).total_seconds()

def granted(
    resource: str, holder: str, ttl_seconds: int, *, reclaimed_stale: bool
) -> dict[str, Any]:
    """A successful claim, said the same way however it was won.

    The two paths into a grant -- an outright atomic create, and a reclaim of a
    holder that outlived its own ttl -- differ only in `reclaimed_stale`; the
    note the holder reads about its obligations is the same either way, and was
    a duplicated literal that could drift.
    """
    return {
        "acquired": True,
        "resource": resource,
        "holder": holder,
        "ttl_seconds": ttl_seconds,
        "reclaimed_stale": reclaimed_stale,
        "note_to_holder": (
            f"you hold this until you release it, or until {ttl_seconds}s pass without a release -- "
            f"whichever first. Past that, anyone else can reclaim it out from under you. Release it "
            f"yourself as soon as you're done, don't rely on the ttl as a normal end-of-use signal."
        ),
    }


def acquire(resource: str, holder: str, ttl_seconds: int, note: str | None, holder_instruction_path: str | None) -> dict[str, Any]:
    if ttl_seconds <= 0:
        raise ValueError(
            f"--ttl-seconds {ttl_seconds} must be positive -- zero or negative makes a lock immediately "
            f"reclaimable by the very next caller, i.e. no mutual exclusion at all"
        )
    port = port_from_resource(resource)
    if port is not None and not port_is_free(port):
        # Something outside this script's own tracking already holds the OS
        # port -- our lock file may well say "free", but it can't be granted.
        # Reuses the same "not acquired" shape as a lock-file contention so
        # every caller (wait's poll loop, claim-port's increment loop)
        # handles it without a special case.
        return {
            "acquired": False,
            "resource": resource,
            "held_by": None,
            "held_by_instruction_path": None,
            "held_note": "occupied by a process outside claim-resource.py's own tracking, not this plugin's lock",
            "age_seconds": 0.0,
            "held_ttl_seconds": 30,
            "retry_after_seconds": 5,
            "held_externally": True,
        }

    path = lock_path(resource)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "resource": resource,
        "holder": holder,
        "holder_instruction_path": holder_instruction_path,
        "note": note,
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": ttl_seconds,
    }

    for attempt in range(2):  # second pass only after losing (or winning) a reclaim race
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                existing = load_json(path)
            except (FileNotFoundError, json.JSONDecodeError):
                # Gone, or mid-write, since our os.open just failed -- a concurrent
                # release/reclaim/gc raced us. Don't guess at content that isn't
                # there; just retry the atomic create fresh against current state.
                continue
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
                    "held_by_instruction_path": existing.get("holder_instruction_path"),
                    "held_note": existing.get("note"),
                    "age_seconds": round(age, 1),
                    "held_ttl_seconds": existing["ttl_seconds"],
                    "retry_after_seconds": max(5, min(30, int(remaining))),
                }
            # Stale -- the previous holder never released and outlived its own ttl.
            # Runs the actual check-and-replace inside a mutex (see
            # with_reclaim_mutex's docstring for why a lock-free version of
            # this specifically was proven unsafe under real concurrency).
            if with_reclaim_mutex(resource, lambda: reclaim_stale(path, payload)):
                return granted(resource, holder, ttl_seconds, reclaimed_stale=True)
            # Lost the race to reclaim -- someone else's write is what's actually
            # on disk now. Loop back and re-observe current state, not stale content.
            continue
        else:
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(payload, indent=2) + "\n")
            # reclaimed_stale is always False here, regardless of attempt number --
            # a successful reclaim already returned from inside the except block
            # above. Reaching this branch (os.open succeeded outright) only ever
            # means nothing existed at this path at that instant, whether that's
            # attempt 0 or attempt 1 after losing an earlier reclaim race.
            return granted(resource, holder, ttl_seconds, reclaimed_stale=False)

    raise ValueError(
        f"could not acquire lock on {resource!r} -- contended again immediately after reclaiming a stale entry, try again"
    )

WAIT_CHURN_MULTIPLIER = 3  # see wait_for's docstring note below

def wait_for(
    resource: str, holder: str, ttl_seconds: int, note: str | None, holder_instruction_path: str | None, max_wait_seconds: int | None
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
    # Seeded with this call's own ttl_seconds, not 0: the external-occupancy
    # branch of acquire() reports a synthetic held_ttl_seconds of 30 (it has
    # no real ttl to report), and letting that alone set the ceiling would
    # cap every fixed-port wait against an untracked occupant at 90s
    # (30 * WAIT_CHURN_MULTIPLIER) regardless of what --ttl-seconds asked
    # for. Seeding with our own budget is a floor, never a shrink -- a real
    # observed holder's larger ttl still raises it via the max() below.
    max_ttl_seen = ttl_seconds
    while True:
        try:
            result = acquire(resource, holder, ttl_seconds, note, holder_instruction_path)
        except ValueError:
            # acquire's own race-exhaustion fallback (two reclaimers colliding
            # on the same stale lock, both attempts lost) -- transient, not a
            # reason to abort a wait whose whole point is to keep trying.
            # Treat it exactly like ordinary contention and poll again shortly.
            time.sleep(5)
            continue
        if result["acquired"]:
            return result
        retry = result["retry_after_seconds"]
        elapsed = time.monotonic() - started
        max_ttl_seen = max(max_ttl_seen, result["held_ttl_seconds"])
        deadline = max_ttl_seen * WAIT_CHURN_MULTIPLIER
        if max_wait_seconds is not None:
            deadline = min(deadline, max_wait_seconds)
        remaining_budget = deadline - elapsed
        instruction_bit = f" (instruction {result['held_by_instruction_path']!r})" if result.get("held_by_instruction_path") else ""
        if result.get("held_externally"):
            who = "an untracked external process"
            # The 30s held_ttl_seconds acquire() reports for this case is a
            # synthetic placeholder, not a real reclaim estimate -- nothing
            # about an untracked occupant "expires" on any schedule we know.
            reclaim_bit = "no way to know when this frees up -- it's outside this script's own tracking"
        else:
            who = f"{result['held_by']!r}{instruction_bit}"
            reclaimable_in = max(0.0, result["held_ttl_seconds"] - result["age_seconds"])
            reclaim_bit = f"reclaimable in ~{reclaimable_in:.0f}s if not released sooner"
        print(
            f"waiting on {resource!r}, held by {who}, retrying in {retry}s "
            f"({elapsed:.0f}s elapsed of {deadline:.0f}s budget; {reclaim_bit})",
            file=sys.stderr,
        )
        if remaining_budget <= 0:
            reason = (
                f"--max-wait-seconds {max_wait_seconds} reached"
                if max_wait_seconds is not None
                else f"{WAIT_CHURN_MULTIPLIER}x the largest ttl_seconds observed ({max_ttl_seen}s) reached -- "
                f"likely several different holders in a row rather than one slow one"
            )
            raise ValueError(f"gave up waiting on {resource!r} after {elapsed:.0f}s -- still held by {who} ({reason})")
        # Clamp the sleep to the remaining budget, not just the poll cadence --
        # otherwise the last sleep before giving up always overshoots the
        # deadline by up to one full retry interval before detecting it.
        time.sleep(min(retry, remaining_budget))

def claim_port(
    app: str,
    key: str,
    base: int,
    port_range: int,
    max_attempts: int,
    holder: str,
    ttl_seconds: int,
    note: str | None,
    holder_instruction_path: str | None,
) -> dict[str, Any]:
    if port_range < 1:
        raise ValueError(f"--range {port_range} must be at least 1")
    highest_possible = base + port_range - 1 + max(0, max_attempts - 1)
    if not (0 < base <= 65535) or highest_possible > 65535:
        raise ValueError(
            f"--base {base} / --range {port_range} / --max-attempts {max_attempts} can reach port "
            f"{highest_possible}, outside the valid 1-65535 range -- lower one of these"
        )
    start = base + int(hashlib.sha256(key.encode()).hexdigest(), 16) % port_range
    candidate = start
    last_result: dict[str, Any] | None = None
    for _ in range(max_attempts):
        resource = f"port--{app}--{candidate}"
        try:
            result = acquire(resource, holder, ttl_seconds, note, holder_instruction_path)
        except ValueError as exc:
            # acquire's own race-exhaustion fallback -- treat this candidate as
            # contended too (same as a normal lock-file collision) and move on,
            # rather than aborting the whole claim-port attempt over one
            # transient race on one candidate.
            last_result = {"acquired": False, "resource": resource, "held_note": str(exc)}
            candidate += 1
            continue
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
    # A single read attempt, not is_file()-then-load_json() -- the two-step
    # check-then-read has its own TOCTOU gap where a concurrent gc/reclaim/
    # release could remove the file in between, and load_json would still
    # raise FileNotFoundError right after is_file() said True.
    try:
        existing = load_json(path)
    except FileNotFoundError:
        raise ValueError(f"no lock held on {resource!r} -- nothing to release")
    except json.JSONDecodeError:
        raise ValueError(f"lock file for {resource!r} is mid-write (empty/partial) -- try again shortly")
    if existing["holder"] != holder and not force:
        raise ValueError(
            f"lock on {resource!r} is held by {existing['holder']!r}, not {holder!r} -- "
            f"refusing to release someone else's lock without --force"
        )
    try:
        path.unlink()
    except FileNotFoundError:
        # Already gone -- a concurrent gc/reclaim/release beat us to it. The
        # resource is free either way, which is what this call promises.
        pass
    return {"released": True, "resource": resource, "was_held_by": existing["holder"]}

def status(resource: str) -> dict[str, Any]:
    path = lock_path(resource)
    try:
        existing = load_json(path)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"held": False, "resource": resource}
    age = age_seconds(existing["acquired_at"])
    return {
        "held": True,
        "resource": resource,
        "holder": existing["holder"],
        "holder_instruction_path": existing.get("holder_instruction_path"),
        "note": existing.get("note"),
        "age_seconds": round(age, 1),
        "expired": age > existing["ttl_seconds"],
    }

def list_locks(prefix: str | None) -> dict[str, Any]:
    locks_dir = straw_boss_root() / "locks"
    if not locks_dir.is_dir():
        return {"locks": []}
    entries = []
    for path in sorted(locks_dir.glob("*.json")):
        resource = path.stem
        if prefix is not None and not resource.startswith(prefix):
            continue
        try:
            existing = load_json(path)
        except (FileNotFoundError, json.JSONDecodeError):
            continue  # raced against a concurrent release/reclaim/gc; skip it
        age = age_seconds(existing["acquired_at"])
        entries.append(
            {
                "resource": resource,
                "holder": existing["holder"],
                "holder_instruction_path": existing.get("holder_instruction_path"),
                "note": existing.get("note"),
                "age_seconds": round(age, 1),
                "expired": age > existing["ttl_seconds"],
            }
        )
    return {"locks": entries}

def gc() -> dict[str, Any]:
    """Deletes every lock already past its own ttl_seconds, regardless of
    whether anyone is currently contending for it. `acquire` already
    reclaims a stale lock reactively the moment anyone asks again -- this
    is purely proactive housekeeping for a resource nobody has re-asked
    for since it went stale, so `list` doesn't stay cluttered with
    long-dead entries indefinitely. Never touches a lock still within its
    own ttl, so it can't remove anything actually live.

    Also sweeps orphaned .reclaim-mutex files (see with_reclaim_mutex) --
    a process that crashes between winning the mutex and its own cleanup
    leaves one behind. The next contender for that same resource already
    self-heals this on its own (the mutex's own staleness check clears it
    after RECLAIM_MUTEX_STALE_SECONDS), but same as a stale lock nobody
    re-asks about, nothing proactively cleans one up if nobody ever
    contends for that resource again."""
    locks_dir = straw_boss_root() / "locks"
    if not locks_dir.is_dir():
        return {"removed": []}
    removed = []
    for path in sorted(locks_dir.glob("*.json")):
        try:
            existing = load_json(path)
        except (FileNotFoundError, json.JSONDecodeError):
            continue  # raced against a concurrent release/reclaim/gc; nothing to sweep here
        age = age_seconds(existing["acquired_at"])
        if age > existing["ttl_seconds"]:
            try:
                path.unlink()
            except FileNotFoundError:
                continue  # someone else already removed it -- not this gc's to report
            removed.append({"resource": path.stem, "holder": existing["holder"], "age_seconds": round(age, 1)})
    for path in sorted(locks_dir.glob("*.json.reclaim-mutex")):
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            continue
        if time.time() - mtime > RECLAIM_MUTEX_STALE_SECONDS:
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            removed.append({"resource": path.name.removesuffix(".json.reclaim-mutex"), "note": "orphaned reclaim-mutex"})
    return {"removed": removed}
