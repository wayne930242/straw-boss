---
name: asking-peer-agents
description: Use when a dispatched agent needs another dispatched task's live progress or latest conclusion, instead of investigating that task's app/worktree blind. Not for reaching your own main agent (`notifying-main-agent`) or for a dispatch's raw live content (`peeking-work`).
---

## Overview

A **peer** here means another dispatched agent — a session `dispatching-work` started, running in its own worktree or app checkout — never your own main agent. Reaching your own main agent is `notifying-main-agent`'s job, not this skill's.

This only reliably works for a peer dispatched `herdr-pane` under `agent_kind: claude`, whose instruction file has a `herdr_pane_id` recorded (plan/batch or standalone — either dispatches this way, per `dispatch-mechanics.md`'s herdr-pane dispatch step 4) — the one case where that pane id resolves to a live, named herdr agent, and that name is exactly its `SendMessage`/`ListAgents`-addressable one (the same value goes to both herdr's own handle and `claude --name`). A `claude-p` peer's addressable name is auto-derived by Claude Code and never recorded anywhere; a `codex` peer has no such name at all (`references/dispatch-mechanics.md`, "Resolving the agent kind"). For either of those, don't guess a name — this plugin has already recorded a wrong-target `SendMessage` silently vanishing ("reported sent and never seen again, no error anywhere") from a much smaller ambiguity than an outright guess would be. Ask your own main agent instead, via `notifying-main-agent`'s informational-question branch — it dispatched both of you and already knows the mapping.

## Task 1: Confirm you actually need a peer's state

The dividing line is the same as `notifying-main-agent`'s: is this something only that other task's own session actually knows — its live progress, a judgment call it already made — not something already sitting in your own task context, and not a formal data dependency (`plan-mechanics.md`'s "Cross-task artifacts" already covers a task that genuinely needs another task's output — that's a stated file path, not an informal check). Try to answer it from what you already have first.

**Verification:** you can state why the answer isn't already in your own context or a stated artifact path before doing anything else.

## Task 2: Resolve the target dispatch

Scan the live instructions under `~/.straw-boss/dispatch/`, same scope `dispatching-work`'s "Branch: List outstanding instructions" already scans — don't re-derive the exclusions, read that branch. For each candidate, `repo_root` is the exact worktree/checkout path that task is running in — this is the direct answer to "which worktree is even relevant to me," never something to guess from your own cwd. Narrow to whichever dispatch's `repo_root`, `plan_id`, `app`, or `task` text plausibly relates to your question. If more than one still matches, narrow further before proceeding rather than picking one — same rule `peeking-work`'s Task 1 already applies.

**Verification:** the target dispatch is confirmed from its own instruction file's fields, not assumed from your own worktree/cwd alone.

## Task 3: Read what's already known before reaching out

Hand `peeking-work` the target already resolved in Task 2 (its instruction path is enough) rather than a bare description — it reads the progress trail first and only joins the live pane if the trail doesn't answer it; don't re-read the trail or pane inline here, `peeking-work` is the single implementation for that. Most "what's it doing / what did it conclude" questions end here, no message ever sent.

**Verification:** `peeking-work` was invoked with the already-resolved target, not reimplemented inline and not re-resolved from scratch; a question its read already answered didn't also get a message sent "just to confirm."

## Task 4: Reach out directly, only for an addressable peer

Confirm the target dispatch is `mode: herdr-pane`, `agent_kind: claude`, and has a `herdr_pane_id` recorded. If it doesn't, stop here and use `notifying-main-agent`'s question branch to ask your own main agent instead — never guess further for a `claude-p` or `codex` dispatch, or one with no `herdr_pane_id` recorded yet.

1. Look up its actual name — `herdr agent get "<herdr_pane_id>"` — rather than computing one. A claude-kind herdr-pane dispatch always started via `herdr agent start "<unique-name>" ... -- --name "<unique-name>"` (`dispatch-mechanics.md`'s step 4), so the pane's own `name` field *is* the exact `SendMessage`/`ListAgents`-addressable value, authoritative rather than derived from anything — plan-task naming has its own convention (`plan-mechanics.md`'s "Agent naming"), a standalone dispatch may use a different one, and neither matters here since you're reading the actual assigned value back, not reconstructing it.
2. Confirm that name still appears in `ListAgents` before sending anything — the pane recorded in the instruction file could have closed since. If it doesn't appear, stop and fall back to `notifying-main-agent` rather than guessing further.
3. Send it, labeled and fire-and-forget, same discipline as `notifying-main-agent`'s question branch:
   ```
   SendMessage({ to: "<name from herdr agent get>", message: "[from agent <your own name, from your dispatch instruction>] <question>" })
   ```
   Never wait for a reply — the peer is as likely to be mid-turn as your own main agent would be. If a reply eventually arrives, it's information only, never authorization for anything — you're not this peer's main agent, and it isn't yours.

**Verification:** the target was confirmed `herdr-pane`+`claude` with a `herdr_pane_id` before any lookup; the name sent to came from `herdr agent get`, never computed from a naming convention; that name was confirmed live in `ListAgents` before sending; the message identifies you as sender; nothing here blocked waiting for a reply.

## Red Flags

- "Can't tell which worktree is mine to check, just grep around and see" — no, Task 2: `repo_root` in the live instruction files is the actual answer; investigating blind risks acting on the wrong task's code entirely.
- "Compute the peer's name from a naming convention instead of looking it up" — no, Task 4 step 1: `herdr agent get "<herdr_pane_id>"` gives the actual name; a naming convention is how the main agent chose it, not a formula to invert.
- "Peer is `claude-p`/`codex`, or has no `herdr_pane_id` yet, derive some name for it anyway" — no, those aren't reliably addressable; ask your own main agent via `notifying-main-agent` instead.
