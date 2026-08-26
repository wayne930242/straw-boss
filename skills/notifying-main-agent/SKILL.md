---
name: notifying-main-agent
description: Route a dispatched agent's questions, progress, and status to its recorded main agent.
---

## Overview

A Herdr-launched session is an independent agent. Discuss work details and
authorization directly with the user; the main agent accepts those decisions.
Ask it only for integrated context or a coordinator-owned action result. Address
every operation by your instruction path.

Live bodies are delta-only and at most two sentences. Put detailed context or
evidence in repeatable `--ref`; transport adds identity, intent, and correlation.

## Ask the main agent

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <your exact instruction path> \
  --to main --intent question \
  --message "<one integration question; include expected reply shape>" \
  --ref "<source or artifact when needed>"
```

Continue independent work. If the coordinator's answer becomes blocking, report
`awaiting-main-agent`; a user-owned question remains `awaiting-user-input`.

## Report status

At every checkpoint and terminal outcome, make exactly one call:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/report-task-status.py" \
  --instruction-path <your exact instruction path> \
  --status <done|failed|awaiting-authorization|awaiting-user-input|awaiting-main-agent> \
  --note "<outcome or exact unblock>" --ref "<proof when needed>"
```

For `done` and `failed`, the command writes first and then notifies the recorded
main-agent Herdr endpoint. Delivery failure is surfaced and leaves durable state
for watcher recovery.

## Report a feature-branch push

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <your exact instruction path> \
  --to main --intent inform \
  --message "Pushed <branch>; continuing." --ref "<MR/PR>"
```

If no live endpoint exists, record the same detail with `report-progress.py`.
Continue immediately.

**Complete when:** the intended message was delivered, or terminal status was
persisted and its Herdr notification succeeded or visibly failed.
