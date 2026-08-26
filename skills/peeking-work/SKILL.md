---
name: peeking-work
description: Use when checking a dispatched task's live progress without joining or interrupting it, or judging whether a stuck/failed task looks like a permission denial. Not for status alone (`dispatching-work`'s list branch).
---

## Overview

Read-only. Never interrupts a `working` pane, never sends input, never substitutes for the actual checkpoint-answering flow — it only tells you what a dispatched task is currently doing. Every straw-boss skill that needs this reads it through here; the pane-read, progress-trail, and transcript-tail mechanics are not reimplemented inline anywhere else.

## Task 1: Resolve the target dispatch

Identify which dispatch to peek at from a task id/plan slug, session id, or
description. Resolve the canonical instruction at
`~/.straw-boss/dispatch/<app>--<slug>.json`; for a plan task, use its
`plan_id`/`task_id` correlation rather than treating the status record as
routing data. The instruction supplies `mode`, `session_id`, and `repo_root`.
For `herdr-pane`, its launch receipt supplies the agent name and pane. Ask the
caller when more than one instruction matches.

**Verification:** the target dispatch is confirmed from its actual instruction/status file, not guessed from a name alone.

## Task 2: Read the progress trail first

Before touching the live pane or transcript, read the dispatch's own progress log — a sibling `<app>--<slug>.progress.jsonl` next to its instruction file (per `dispatch-mechanics.md`'s "Reporting scripts"), written by the dispatched agent's own `report-progress.py` calls throughout its work. Tail it (most recent few entries) rather than dumping the whole file. For a plan task, also check its status file — a terminal or checkpoint status there answers the question outright.

If the trail (plus, for a plan task, the status file) already answers "what's it doing" — a recent note, a clear status — that's your answer; skip Task 3 entirely. This is the whole point of the trail existing: most peeks shouldn't need to join the dispatched agent's live pane at all.

**Verification:** the trail was checked before any live read was attempted; a peek that the trail already answered did not also do a live read "just to be thorough."

## Task 3: Peek live, only when the trail doesn't answer it

Follow `references/peek-mechanics.md` for the exact command — don't improvise the transcript path encoding or the `herdr agent read` flags from memory.

- `herdr-pane` → `herdr agent read`, read-only, doesn't interrupt.
- `claude-p` → tail the agent's own transcript jsonl; there's no pane to read.

**Verification:** the mechanism used matches the dispatch's actual mode; nothing was typed or sent into the target pane; this task only ran because Task 2's trail genuinely didn't answer the question (empty, stale, or too vague), not out of habit.

## Task 4: Report

Summarize what the agent is currently doing in plain language — not a raw dump of the trail or read/tail output. If the peek shows the agent is effectively stuck on something its status file hasn't caught up to yet, say so — but don't act on it here: resolving a checkpoint goes through the agent's own pane, or `dispatching-work`'s checkpoint handling, not this skill.

**Verification:** the caller gets a plain-language answer to "what's it doing", not unfiltered raw output.

## References

- `references/peek-mechanics.md` — exact `herdr agent read` syntax, transcript path encoding, and extraction for `claude-p`.
