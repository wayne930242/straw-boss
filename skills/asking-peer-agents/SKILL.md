---
name: asking-peer-agents
description: Use when a dispatched agent needs another dispatched task's live progress or latest conclusion. Herdr is primary for Claude or Codex peer panes; SendMessage is a Claude-to-Claude fallback only.
---

## Overview

A **peer** here means another dispatched agent — a session `dispatching-work`
started, running in its own worktree or app checkout — never your own main
agent. Reaching your own main agent is `notifying-main-agent`'s job, not this
skill's.

A peer is directly reachable when its instruction records `mode: herdr-pane`,
`agent_kind: claude` or `agent_kind: codex`, and `herdr_pane_id`. Prompt that
exact pane through herdr. A `claude-p` dispatch has no peer pane id, so ask your
own main agent through `notifying-main-agent` instead. Never derive a pane id,
provider, or peer name.

## Task 1: Confirm you actually need a peer's state

The dividing line is the same as `notifying-main-agent`'s: is this something only that other task's own session actually knows — its live progress, a judgment call it already made — not something already sitting in your own task context, and not a formal data dependency (`plan-mechanics.md`'s "Cross-task artifacts" already covers a task that genuinely needs another task's output — that's a stated file path, not an informal check). Try to answer it from what you already have first.

**Verification:** you can state why the answer isn't already in your own context or a stated artifact path before doing anything else.

## Task 2: Resolve the target dispatch

Scan the live instructions under `~/.straw-boss/dispatch/`, same scope `dispatching-work`'s "Branch: List outstanding instructions" already scans — don't re-derive the exclusions, read that branch. For each candidate, `repo_root` is the exact worktree/checkout path that task is running in — this is the direct answer to "which worktree is even relevant to me," never something to guess from your own cwd. Narrow to whichever dispatch's `repo_root`, `plan_id`, `app`, or `task` text plausibly relates to your question. If more than one still matches, narrow further before proceeding rather than picking one — same rule `peeking-work`'s Task 1 already applies.

**Verification:** the target dispatch is confirmed from its own instruction file's fields, not assumed from your own worktree/cwd alone.

## Task 3: Read what's already known before reaching out

Hand `peeking-work` the target already resolved in Task 2 (its instruction path is enough) rather than a bare description — it reads the progress trail first and only joins the live pane if the trail doesn't answer it; don't re-read the trail or pane inline here, `peeking-work` is the single implementation for that. Most "what's it doing / what did it conclude" questions end here, no message ever sent.

**Verification:** `peeking-work` was invoked with the already-resolved target, not reimplemented inline and not re-resolved from scratch; a question its read already answered didn't also get a message sent "just to confirm."

## Task 4: Reach out through the recorded peer pane

Confirm the target dispatch is `mode: herdr-pane`, uses a supported
`agent_kind` (`claude` or `codex`), and records `herdr_pane_id`. If any check
fails, use `notifying-main-agent`'s question branch instead.

1. Send the labeled question directly to the recorded pane, without `--wait`:

   ```bash
   herdr agent prompt "<herdr_pane_id>" \
     "[from agent <your own name, from your dispatch instruction>] <question>"
   ```

2. If herdr succeeds, stop. Do not also send `SendMessage`.
3. If herdr fails, `SendMessage` is a Claude-to-Claude fallback only: both your
   own dispatch and the target dispatch must record `agent_kind: claude`.
   Resolve the target's actual name with `herdr agent get "<herdr_pane_id>"`,
   confirm it still appears in `ListAgents`, then send exactly once:

   ```text
   SendMessage({ to: "<name from herdr agent get>", message: "[from agent <your own name>] <question>" })
   ```

4. If either endpoint is Codex, the target is no longer live, or no verified
   name exists, report the failed peer reachability to your own main agent
   through `notifying-main-agent`. Never guess another route.

Both channels are fire-and-forget. A later reply is information only, never
authorization — neither peer is the other's main agent.

**Verification:** the target pane id and provider came from its instruction;
herdr was attempted first for either supported provider; any `SendMessage`
fallback had two confirmed Claude endpoints and a live name read from herdr;
the question identified its sender and did not block waiting for a reply.

## Red Flags

- "Can't tell which worktree is mine to check, just grep around and see" — no, Task 2: `repo_root` in the live instruction files is the actual answer; investigating blind risks acting on the wrong task's code entirely.
- "Convert every pane id to a Claude peer name before sending" — no; prompt
  the recorded herdr pane directly, regardless of whether it runs Claude or
  Codex.
- "Herdr succeeded, also send `SendMessage` for safety" — no; one successful
  delivery is sufficient.
- "One endpoint is Codex, but the peer has a plausible Claude name" — no;
  `SendMessage` is a Claude-to-Claude fallback only.
- "The peer is `claude-p`, so derive a name anyway" — no; without a recorded
  peer pane, ask your own main agent.
