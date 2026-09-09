---
name: contacting-orchestrators
description: Register this orchestrator's identity and one-line scope in the machine's orchestrator directory, read which other orchestrators are live, and send one of them a factual delta that carries this session's herdr pane id. Use before this session's first dispatch, and whenever another orchestrator's work meets this one's.
---

## Register before dispatching

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/register-orchestrator.py" \
  --scope '<one line: the main work this orchestrator owns>'
```

Run this while resolving this session's own reachability, before the first
dispatch. It records this session's herdr pane, provider fingerprint, agent
name, and cwd against that scope, then returns the directory. Re-run it when the
scope moves; the same record is updated in place.

`dispatch-task.py write` seeds a fallback record from this dispatch's own task
text if this session skipped this step -- run it anyway for a scope that
actually names this session's work instead of one dispatch's task line; it
overwrites the fallback in place.

## Read who else is coordinating

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/register-orchestrator.py" --list
```

Each row carries a name, herdr pane, one-line scope, and `live`. A `live: false`
row is a session that has ended: its record stays as history, and its address
reaches nobody. A live row's pane is read from herdr, so it stays right across a
coordinator that moved panes.

## Send one delta

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-orchestrator-message.py" \
  --to <name-or-pane> --intent inform|question|answer \
  --message '<delta>' [--ref '<source>'] [--in-reply-to <id>]
```

The body is one fact, question, or answer in at most two sentences; detail
travels as repeatable `--ref`. The envelope names this session and its herdr
pane id, so the receiver already holds the address to answer on. A target whose
session has ended records the message undelivered in its ledger and reports that
back.

## Answer what arrives

An incoming `[orchestrator <intent> id=<id> from=<name> pane=<pane>] …` line
comes from another coordinator. Reply with `--to <that name or pane> --intent
answer --in-reply-to <that id>`; the id is checked against the question this
session actually received.

## What travels between orchestrators

Verifiable facts: the scope this session owns, a change it landed in a shared
app, a dependency another orchestrator's task is waiting on. Work direction
stays inside each orchestrator's own loop with its workers, and authorization
stays with the user. Two orchestrators whose facts disagree take that to the
user.

**Complete when:** this session holds a current record, and each delta it owed
another orchestrator is delivered or recorded undelivered.
