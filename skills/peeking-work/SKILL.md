---
name: peeking-work
description: Use to read a dispatched task's progress when asked or when evidence disagrees with its recorded state.
---

## Read progress

Resolve one canonical instruction from the task, plan, or session identity using [peek mechanics](references/peek-mechanics.md).
Ask when several instructions match.

Read its status and the recent entries of its sibling `.progress.jsonl` first.
If these answer the question, report that result.
Otherwise use the reference's read-only `herdr agent read` command.

Summarize current activity and any evidence/status discrepancy.
Checkpoint resolution returns to [dispatching-work](../dispatching-work/SKILL.md#handle-events).

**Complete when:** the caller has an evidence-backed progress answer or the specific reason the dispatch cannot be read.
