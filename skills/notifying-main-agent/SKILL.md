---
name: notifying-main-agent
description: Route a dispatched agent's questions, progress, and status to its recorded main agent.
---

## Overview

Discuss work details and authorization directly with the user. Use this skill
only when no direct user channel exists or the main agent must supply integrated
instructions, cross-task context, or a coordinator-owned action. Address every
operation by your instruction path.

## Ask the main agent

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <your exact instruction path> \
  --to main --intent question \
  --message "<needed context and exact integration question>"
```

Continue independent work. If the coordinator's answer becomes blocking, report
`awaiting-main-agent`; a user-owned question remains `awaiting-user-input`.

## Report status

At every checkpoint and terminal outcome, make exactly one call:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/report-task-status.py" \
  --instruction-path <your exact instruction path> \
  --status <done|failed|awaiting-authorization|awaiting-user-input|awaiting-main-agent> \
  --note "<outcome and verification, or blocker and exact unblock>"
```

The command writes before notifying. Delivery failure leaves durable status.

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/report-progress.py" \
  --instruction-path <your exact instruction path> --note "<text>"
```

## Report a feature-branch push

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <your exact instruction path> \
  --to main --intent inform \
  --message "PUSHED: <branch> — <MR/PR reference> — continuing"
```

If no live endpoint exists, record the same detail with `report-progress.py`.
Continue immediately.

**Complete when:** the intended message or durable status exists; terminal work
always has a terminal status report.
