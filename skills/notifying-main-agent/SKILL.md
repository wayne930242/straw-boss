---
name: notifying-main-agent
description: Route a dispatched agent's questions, progress, and status to its recorded main agent.
---

## Overview

Use the dispatch instruction path as the only address. Repository scripts own
the receiver pane, session fingerprint, provider adapter, and delivery record.
See `docs/roles.md` for authority; a delivered reply is information, never
authorization for a gated mutation.

## Branch: Ask a non-blocking question

Use this for a fact the main agent already knows and continue any independent
work while waiting:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <your exact instruction path> \
  --to main --intent question --message "<self-contained question>"
```

If delivery fails and the answer becomes blocking, write an
`awaiting-main-agent` checkpoint. Never substitute a guessed endpoint.

**Verification:** the command succeeded, or the blocking state is durable.

## Branch: Report your own status

At every checkpoint and terminal outcome, make exactly one call:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/report-task-status.py" \
  --instruction-path <your exact instruction path> \
  --status <done|failed|awaiting-authorization|awaiting-user-input|awaiting-main-agent> \
  --note "<self-contained summary or blocker>"
```

The command writes durable status first, then uses the shared transport when a
live main-agent endpoint exists. A delivery error preserves the status for the
watcher/process recovery path.

Progress notes remain separate and non-terminal:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/report-progress.py" \
  --instruction-path <your exact instruction path> --note "<text>"
```

**Verification:** the status command names the written file; a final chat
response or progress note alone is never completion.

## Branch: Report a feature-branch push and continue

A push of the task's own feature branch is an FYI, not a status transition:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <your exact instruction path> \
  --to main --intent inform \
  --message "PUSHED: <branch> — <MR/PR reference> — continuing"
```

If no live endpoint exists, record the same detail with `report-progress.py`.
Continue immediately.

## Red flags

- A pane id, session id, agent name, or provider appears in a communication
  command — use the instruction-keyed script.
- A notification error is treated as lost status — inspect the preserved file.
- A reply is treated as authorization — enter the required checkpoint flow.
- Work is complete but no terminal status command ran — report before stopping.
