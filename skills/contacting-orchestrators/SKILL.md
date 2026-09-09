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
name, and cwd against that scope, then returns the directory. Re-run it when
the scope moves; the same record is updated in place.

When a Claude pane's terminal title carries no session, registration resolves
one from the herdr foreground Claude process's PID against
`~/.claude/sessions/<pid>.json` (or `CLAUDE_CONFIG_DIR`), reading the
interactive CLI session. Listing and sending share that source, and a send
re-checks the actual recipient before it goes out. When no verifiable session
is available, registration reports why the orchestrator is unaddressable.

`dispatch-task.py write` seeds a fallback record from this dispatch's own task
text if this session skipped this step -- run it anyway for a scope that
actually names this session's work instead of one dispatch's task line; it
overwrites the fallback in place.

## Read who else is coordinating

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/register-orchestrator.py" --list
```

Each row carries a name, herdr pane, one-line scope, and `live`. A `live: false`
row has no verified live match: its record stays as history, its address
reaches nobody, and `unavailable_reason` explains the missing match. A live row's pane is read from herdr, so it stays right across a
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

Don't verify another orchestrator's claims. Act on a peer's report of work
inside its own scope as given — a peer that reports it confirmed a deployment's
allocation healthy has settled that, and each line stays independent. The
premises of your own decisions remain yours to check: whether a fix has landed
on `develop` gates whether this line can merge, so check that branch. Facts
that actually disagree go to the user, per the rule above.

**Complete when:** this session holds a current record, and each delta it owed
another orchestrator is delivered or recorded undelivered.
