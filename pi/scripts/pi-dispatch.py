#!/usr/bin/env python3
"""Inspect and recover Pi dispatches recorded by the local extension."""

import argparse
from contextlib import contextmanager
import json
import os
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path


AGENT_DIR = Path(os.environ.get("PI_CODING_AGENT_DIR", str(Path.home() / ".pi/agent")))
LEDGER_DIR = AGENT_DIR / "dispatch-ledger"
HANDOFF_DIR = AGENT_DIR / "handoffs"
SUBAGENT_EXTENSION = AGENT_DIR / "npm/node_modules/pi-herdr-agents/pi-extension/subagents/subagent-done.ts"
# Pause between Herdr readiness polls; the attempt counts stay fixed, so tests
# driving an instant fake Herdr shorten only the wall-clock budget.
POLL_SECONDS = float(os.environ.get("PI_DISPATCH_POLL_SECONDS", "0.2"))


def session_id(value):
    result = value or os.environ.get("PI_SESSION_ID")
    if not result:
        raise ValueError("Pass --session-id from the Pi dispatch_control tool")
    return result


def ledger_path(owner):
    return LEDGER_DIR / f"{owner}.json"


def read_ledger(owner):
    path = ledger_path(owner)
    return json.loads(path.read_text()) if path.exists() else []


def committed_dispatch_ids(owner):
    ids = set()
    if HANDOFF_DIR.exists():
        for path in HANDOFF_DIR.glob("*.json"):
            handoff = json.loads(path.read_text())
            if handoff.get("state") == "committed" and handoff.get("from") == owner:
                ids.update(record["id"] for record in handoff.get("dispatches", []))
    return ids


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(data, indent=2) + "\n")
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def lock_ledger(owner):
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    lock = LEDGER_DIR / f".{owner}.lock"
    deadline = time.monotonic() + 5
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Timed out waiting for dispatch ledger {owner}")
            time.sleep(0.01)
    try:
        yield
    finally:
        lock.rmdir()


def herdr(*args):
    if os.environ.get("HERDR_ENV") != "1":
        raise ValueError("Herdr is unavailable; open Pi in a Herdr pane first")
    try:
        result = subprocess.run(["herdr", *args], check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        raise RuntimeError(f"herdr {' '.join(args[:2])} failed: {detail}") from error
    return json.loads(result.stdout) if result.stdout.strip() else {}


def new_pane(cwd, label, env=None):
    args = ["tab", "create", "--cwd", cwd, "--label", label, "--no-focus"]
    workspace = os.environ.get("HERDR_WORKSPACE_ID")
    if workspace:
        args.extend(["--workspace", workspace])
    if env:
        for key, value in env.items():
            args.extend(["--env", f"{key}={value}"])
    response = herdr(*args)
    pane = response["result"]["root_pane"]["pane_id"]
    for _ in range(25):
        try:
            processes = herdr("pane", "process-info", "--pane", pane)["result"]["process_info"]["foreground_processes"]
        except RuntimeError:
            processes = []
        if any(item.get("name") in ("zsh", "bash", "fish", "sh") for item in processes):
            return pane
        time.sleep(POLL_SECONDS)
    raise RuntimeError(f"New pane {pane} did not reach an interactive shell")


def pane_available(pane):
    try:
        response = herdr("pane", "process-info", "--pane", pane)
    except RuntimeError:
        return None
    processes = response["result"]["process_info"]["foreground_processes"]
    return not processes or all(item.get("name") in ("zsh", "bash", "fish", "sh") for item in processes)


def start_receiving_agent(name, pane):
    for attempt in range(25):
        try:
            herdr("agent", "start", name, "--kind", "pi", "--pane", pane, "--", "--name", name)
            return
        except RuntimeError as error:
            if "agent_pane_busy" not in str(error) or attempt == 24:
                raise
            time.sleep(POLL_SECONDS)


def roll_call(owner):
    records = read_ledger(owner)
    transferred = committed_dispatch_ids(owner)
    for item in records:
        pane = item.get("paneId") or "unknown"
        status = "transferred" if item["id"] in transferred else item["status"]
        print(f"{item['id']} | {status} | {item['name']} | {pane} | {item['sessionFile']}")
    if not records:
        print("No recorded dispatches")


def reattach(owner, dispatch_id):
    records = read_ledger(owner)
    item = next((record for record in records if record["id"] == dispatch_id), None)
    if not item:
        raise ValueError(f"Unknown dispatch: {dispatch_id}")
    if item["status"] != "running" or dispatch_id in committed_dispatch_ids(owner):
        status = "transferred" if dispatch_id in committed_dispatch_ids(owner) else item["status"]
        raise ValueError(f"Dispatch is {status}; inspect its recorded session")
    pane = item.get("paneId")
    available = pane_available(pane) if pane else None
    if pane and available is False:
        raise ValueError(f"Pane {pane} still has a foreground process; inspect it before resuming")
    if available is None:
        previous_pane = item.get("paneId")
        pane = new_pane(item["cwd"], f"resume-{item['name']}")
        stale = False
        with lock_ledger(owner):
            records = read_ledger(owner)
            item = next((record for record in records if record["id"] == dispatch_id), None)
            stale = (not item or item["status"] != "running" or
                     item.get("paneId") != previous_pane or dispatch_id in committed_dispatch_ids(owner))
            if not stale:
                item["paneId"] = pane
                write_json(ledger_path(owner), records)
        if stale:
            try:
                herdr("pane", "close", pane)
            except RuntimeError:
                pass
            raise ValueError(f"Dispatch {dispatch_id} changed while opening its pane; inspect its recorded session")
    env = {
        "PI_SUBAGENT_SESSION": item["sessionFile"],
        "PI_SUBAGENT_ID": item["id"],
        "PI_SUBAGENT_NAME": item["name"],
        "PI_SUBAGENT_AUTO_EXIT": "1",
        "PI_SUBAGENT_SURFACE": pane,
    }
    args = ["pi", "--session", item["sessionFile"]]
    if SUBAGENT_EXTENSION.exists():
        args += ["-e", str(SUBAGENT_EXTENSION)]
    args += ["Continue the assigned task from this session. Report the result when complete."]
    command = "cd " + shlex.quote(item["cwd"]) + " && " + " ".join(f"{key}={shlex.quote(value)}" for key, value in env.items()) + " " + shlex.join(args)
    herdr("pane", "run", pane, command)
    print(f"Resumed {item['name']} in {pane}; completion will be delivered to the owner session")


def handoff(owner, cwd, summary):
    transfer_id = uuid.uuid4().hex
    handoff_file = HANDOFF_DIR / f"{transfer_id}.json"
    ready_file = HANDOFF_DIR / f"{transfer_id}.ready"
    write_json(handoff_file, {"from": owner, "summary": summary, "state": "pending"})
    pane = None
    committed = False
    name = f"handoff-{transfer_id[:8]}"
    try:
        pane = new_pane(cwd, name, {"PI_HANDOFF_ID": transfer_id})
        start_receiving_agent(name, pane)
        for _ in range(50):
            if ready_file.exists():
                break
            time.sleep(POLL_SECONDS)
        else:
            raise RuntimeError(f"Receiving agent {name} did not load dispatch recovery")
        prompt = (f"You are taking over a main-agent scope. Handoff ID: {transfer_id}. "
                  f"Summary: {summary} Use dispatch_control roll-call to inspect the transferred "
                  "dispatches after this handoff commits, then continue the work.")
        herdr("agent", "prompt", name, prompt)
        with lock_ledger(owner):
            current = read_ledger(owner)
            already_transferred = committed_dispatch_ids(owner)
            records = [record.copy() for record in current
                       if record["status"] == "running" and record["id"] not in already_transferred]
            # The committed handoff file is the atomic ownership decision. The old
            # ledger is a view of it and can be repaired after an interrupted write.
            write_json(handoff_file, {"from": owner, "summary": summary,
                                      "state": "committed", "dispatches": records})
            committed = True
            record_ids = {record["id"] for record in records}
            for record in current:
                if record["id"] in record_ids:
                    record["status"] = "transferred"
            try:
                write_json(ledger_path(owner), current)
            except OSError as error:
                # The committed handoff remains authoritative and roll-call reads it.
                print(f"Handoff {transfer_id} committed; old ledger view update failed: {error}", file=sys.stderr)
    except Exception:
        if not committed:
            handoff_file.unlink(missing_ok=True)
            ready_file.unlink(missing_ok=True)
            if pane:
                try:
                    herdr("pane", "close", pane)
                except RuntimeError:
                    pass
        raise
    print(f"Handoff {transfer_id} started in pane {pane}; active dispatches: {len(records)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("roll-call", "reattach", "handoff"))
    parser.add_argument("id", nargs="?")
    parser.add_argument("--session-id")
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--summary")
    args = parser.parse_args()
    owner = session_id(args.session_id)
    if args.action == "roll-call":
        roll_call(owner)
    elif args.action == "reattach":
        if not args.id:
            parser.error("reattach requires a dispatch ID")
        reattach(owner, args.id)
    else:
        if not args.summary:
            parser.error("handoff requires --summary")
        handoff(owner, args.cwd, args.summary)


if __name__ == "__main__":
    main()
