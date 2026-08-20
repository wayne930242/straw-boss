---
name: peeking-work
description: Use when checking a dispatched task's live progress without joining or interrupting it, or judging whether a stuck/failed task looks like a permission denial. Not for status alone (`dispatching-work`'s list branch).
---

## Overview

Read-only. Never interrupts a `working` pane, never sends input, never substitutes for the actual checkpoint-answering flow — it only tells you what a dispatched task is currently doing. Every straw-boss skill that needs this reads it through here; the pane-read, progress-trail, and transcript-tail mechanics are not reimplemented inline anywhere else.

## Task 1: Resolve the target dispatch

Identify which dispatch to peek at — from a task_id/plan slug, a session_id, or a description the caller gave you. Read its instruction file (`~/.straw-boss/dispatch/<app>--<slug>.json`, or the plan status file under `~/.straw-boss/plans/<slug>/status/` for a plan task) to get its `mode`, `session_id`, `cwd`, and — for `herdr-pane` — its agent name. Ask the caller if more than one dispatch could match.

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

## Red Flags

- "Peeked, now let me just fix it directly in that pane" — no, peeking is read-only; anything more goes through the actual checkpoint/dispatch flow.
- "Just eyeball the status label instead of peeking" — that's `dispatching-work`'s list branch, a shallower, different answer.
- "Reconstruct the transcript path or herdr flags from memory" — no, always `references/peek-mechanics.md`.
- "This other skill needs a quick peek, just inline a read here instead of calling peeking-work" — no, every peek in this plugin goes through this skill; no duplicate implementations.
- "Skip the progress trail, just read the live pane, it's more thorough anyway" — no, Task 2: check the trail first; a live read that wasn't actually needed interrupts nothing technically but defeats the reason the trail exists — most peeks should be answerable from it alone.
- "No progress log file yet, treat that as the task being stuck" — no, the log is only created on the dispatched agent's first `report-progress.py` call; an empty/missing trail just means it hasn't logged anything yet (or is a task predating this convention) — fall through to Task 3, don't diagnose from absence alone.

## References

- `references/peek-mechanics.md` — exact `herdr agent read` syntax, transcript path encoding, and extraction for `claude-p`.
