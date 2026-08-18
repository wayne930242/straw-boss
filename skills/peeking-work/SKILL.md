---
name: peeking-work
description: Use when checking a dispatched task's live progress without joining or interrupting it, or judging whether a stuck/failed task looks like a permission denial. Not for status alone (`dispatching-work`'s list branch).
---

## Overview

Read-only. Never interrupts a `working` pane, never sends input, never substitutes for the actual checkpoint-answering flow — it only tells you what a dispatched task is currently doing. Every straw-boss skill that needs this reads it through here; the pane-read and transcript-tail mechanics are not reimplemented inline anywhere else.

## Task 1: Resolve the target dispatch

Identify which dispatch to peek at — from a task_id/plan slug, a session_id, or a description the caller gave you. Read its instruction file (`~/.straw-boss/dispatch/<session_id>.json`, or the plan status file under `~/.straw-boss/plans/<slug>/status/` for a plan task) to get its `mode`, `session_id`, `cwd`, and — for `herdr-pane` — its agent name. Ask the caller if more than one dispatch could match.

**Verification:** the target dispatch is confirmed from its actual instruction/status file, not guessed from a name alone.

## Task 2: Peek, by mode

Follow `references/peek-mechanics.md` for the exact command — don't improvise the transcript path encoding or the `herdr agent read` flags from memory.

- `herdr-pane` → `herdr agent read`, read-only, doesn't interrupt.
- `claude-p` → tail the agent's own transcript jsonl; there's no pane to read.

**Verification:** the mechanism used matches the dispatch's actual mode; nothing was typed or sent into the target pane.

## Task 3: Report

Summarize what the agent is currently doing in plain language — not a raw dump of the read/tail output. If the peek shows the agent is effectively stuck on something its status file hasn't caught up to yet, say so — but don't act on it here: resolving a checkpoint goes through the agent's own pane, or `dispatching-work`'s checkpoint handling, not this skill.

**Verification:** the caller gets a plain-language answer to "what's it doing", not unfiltered raw output.

## Red Flags

- "Peeked, now let me just fix it directly in that pane" — no, peeking is read-only; anything more goes through the actual checkpoint/dispatch flow.
- "Just eyeball the status label instead of peeking" — that's `dispatching-work`'s list branch, a shallower, different answer.
- "Reconstruct the transcript path or herdr flags from memory" — no, always `references/peek-mechanics.md`.
- "This other skill needs a quick peek, just inline a read here instead of calling peeking-work" — no, every peek in this plugin goes through this skill; no duplicate implementations.

## References

- `references/peek-mechanics.md` — exact `herdr agent read` syntax, transcript path encoding, and extraction for `claude-p`.
