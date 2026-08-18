---
name: dispatching-work
description: Dispatches a resolved app + task to a session actually rooted in that app's own directory (headless claude -p, or an interactive herdr pane), instead of working in the caller's own session against a summary. Also drives a whole plan's wave-by-wave dispatch when work-on produced one, lists outstanding dispatches, and wraps one up when it's done. Use after work-on has resolved the target app(s) (or a plan) for shipping-task/troubleshooting-app, when the user asks what's currently dispatched or how a plan is progressing, or when a dispatched task should be closed out.
---

## Overview

Every dispatched task is tracked as one instruction file under `~/.straw-boss/dispatch/` — the user's home directory, not the target project checkout (see `init`). This skill covers: **dispatch** a single task (Tasks 1-5), **dispatch a plan** (Branch below, when `work-on` produced a multi-task dependency graph), **list**, and **wrap up**. Exact CLI/JSON syntax lives in `references/` — `dispatch-mechanics.md` (single-task + permission-mode detection), `plan-mechanics.md` (plan/status schemas, worktree repair heredoc, zsh `Monitor` gotchas), `cross-session-coordination.md` (`SendMessage`/interrupt syntax) — read the relevant one for the exact command before running it. Every requirement below is real, not a pointer to go read something else first.

Prerequisite: `~/.straw-boss/capability.json` must exist. If it doesn't, stop and tell the caller to run `init` first.

## Task 1: Choose the dispatch mode

- **Self-contained, clear scope, no open question** → `claude-p`, regardless of herdr availability.
- **Complex, error-prone, or likely to need back-and-forth** → `herdr-pane` is required, not preferred — a `claude -p` process cannot pause mid-task for a live reply, so `claude-p` silently forecloses asking instead of guessing. Requires BOTH `capability.json` says `herdr-enabled` AND this session's own `HERDR_ENV` is `1`. If either is false, tell the user headless dispatch can't ask mid-task questions for this one (it reports `failed` with the question stated instead of pausing) and let them decide.

State the mode and why before doing anything else.

**Before the first `herdr-pane` dispatch in this orchestrator session** (not per-dispatch, not per-plan), ensure the orchestrator itself is addressable — see `references/cross-session-coordination.md` "Making the orchestrator addressable" for the exact mechanism. Skipping this is not a cosmetic gap: `SendMessage` does not fail loudly when a worker guesses the wrong target — it silently delivers to whatever session across the account happens to share a similar auto-derived title, which can be a stale, unrelated, offline session. Confirmed live: exactly this happened — a worker's coordination question was reported "sent" and was never seen again, no error anywhere.

**Verification:** mode stated with a reason; `herdr-pane` never chosen without checking both conditions; a task likely to need clarification never silently went to `claude-p` when herdr was available; before the first `herdr-pane` dispatch this session, the orchestrator's own addressability was checked, not assumed.

## Task 2: Resolve batch membership

Several dispatches for one multi-app unit of work share a `batch` label (herdr-pane tab grouping only). A standalone dispatch has none.

## Task 3: Write the instruction, before dispatching

Call `dispatch-task.py write` (schema in `references/dispatch-mechanics.md`) — generates the session_id, writes the instruction (`status: pending`), and for a plan task marks `plan.json` `dispatched`, refusing before writing anything if that task isn't still `planned`. Never hand-write the JSON or generate a second UUID — the script is what keeps a rejected dispatch from leaving a stray file behind.

**Verification:** instruction exists with `pending` status before any `claude`/`herdr` command runs.

## Task 4: Dispatch

Follow `references/dispatch-mechanics.md` for the exact `claude`/`herdr` command sequence — don't improvise it from general knowledge.

**Mirror the orchestrator's own permission mode onto the worker.** Detect it from the orchestrator's own process args (`ps -p "$CLAUDE_PID" -ww -o args=`, exact detection in the reference) and pass the equivalent flag to the worker's launch command. A worker must never end up more tightly gated than the orchestrator dispatching it — never hardcode a specific mode here, and never omit this "to be safe."

For `herdr-pane`, a `herdr agent prompt` success return is not proof of delivery — a first-run interruption can swallow the submission while the CLI still reports success. Confirm delivery (terminal-title check, in the reference) before proceeding.

Once dispatch succeeds and delivery is confirmed, call `dispatch-task.py confirm` — flips to `in-progress`, records pane/tab ids for `herdr-pane`.

**Verification:** status is `in-progress`; permission mode was detected and mirrored, not hardcoded or skipped; pane/tab ids recorded for `herdr-pane`; session_id cross-checked against what herdr reports.

## Task 5: Report

Tell the user what was dispatched, in which mode, and how to find it (instruction path; pane/tab for `herdr-pane`).

## Branch: Dispatch a plan

Plans have their own file formats and a wave-scheduling step Tasks 1-5 don't — don't improvise this by analogy.

**Wave dispatch.** Compute the ready wave (`read-plan-status.py --ready`) and dispatch **every task in it at once** — never one at a time, never serialize an independent task through another task's session because it happens to be idle. Each task still goes through Tasks 1-5 individually (mode selection, instruction, dispatch, confirm), with `plan_id`/`task_id` added.

**Worktree ownership (full-flow tasks).** The orchestrator creates every worktree itself, for every managed app uniformly, regardless of the app's own tooling — plain `git worktree add`, never `herdr worktree create` (it always opens a new herdr workspace with no way to target an existing one; confirmed via herdr's own API schema and [GitHub Discussion #553](https://github.com/herdrdev/herdr/discussions/553)). Verify `git rev-parse --show-toplevel` inside it resolves to the worktree's own path — repos with `extensions.worktreeConfig = true` silently don't, regardless of creation method — and repair with a `config.worktree` file if not (exact steps in `plan-mechanics.md`). Never dispatch into an unverified worktree. For `herdr-pane`, join it to the orchestrator's own existing workspace as a tab (`herdr tab create --workspace`) — a plan's worktrees never scatter across workspaces, and the shared workspace is never closed by this mechanism, only the tabs added to it.

**Worker naming.** Derive from `plan_id`/`task_id` for both herdr's own agent handle and the trailing `claude --name` flag — the same value serves herdr control (`agent get/prompt/read`) and `SendMessage`/`ListAgents` addressability, no separate naming decision.

**Cross-task artifacts.** When task B depends on task A and genuinely needs A's output, both dispatch instructions state the exact path under `~/.straw-boss/plans/<slug>/artifacts/` — A's says where to write it, B's says where to read it and that it's required input, not optional context. `plan.json`'s `description` field is prose, not a handoff mechanism.

**Three checkpoint types — never conflate them:**
| Status | For | Answered by | Terminal? |
|---|---|---|---|
| `awaiting-authorization` | commit/push/merge | User, relayed through the orchestrator (`shipping-task`) | No — orchestrator resumes after authorizing |
| `awaiting-user-input` | work-content question needing human judgment | User, directly in the worker's own pane — orchestrator only points at it | No — worker continues on its own once answered |
| `SendMessage` to the orchestrator | informational question the orchestrator can answer from what it already knows | Orchestrator itself, no human needed (`references/cross-session-coordination.md`) | Not a status transition at all |

A task unsure which applies tries to resolve it itself or asks the orchestrator via `SendMessage` first — only escalate to `awaiting-user-input` when neither the worker nor the orchestrator can actually answer it. Both status checkpoints are `herdr-pane`-only; `claude-p` cannot pause for either.

**Same-task continuation.** Only for phase 2 of the *same* logical task on an idle finished session — never for a different, independent task. Send `/compact [focus]` and the phase-2 text as **two separate** `herdr agent prompt` calls; don't wait for compact to finish before sending the second.

**Monitor coverage.** Start a `Monitor` that emits on every status a task can report — `done`, `failed`, `awaiting-authorization`, `awaiting-user-input` — not just completion (exact zsh-safe polling command in `plan-mechanics.md`). Only `done`/`failed` are terminal: on those, auto-detach (close the pane/worktree tab per the rules above, call `wrap-up-task.py`, recompute + dispatch the next ready wave). `awaiting-authorization`/`awaiting-user-input` never trigger auto-detach. On `failed`, if it looks like a permission denial, ask the user before ever redispatching with a bypass — never automatic. The plan is done only once every task is terminal, never on the first one finishing.

**Port/HMR caveat.** Every worktree-backed instruction states, verbatim or equivalent: a local dev server in this worktree may collide with another worktree's or the shared environment's port/HMR — no port is auto-allocated.

**Verification:** every ready-wave task dispatched together; a task with unresolved dependencies never dispatched early; worktree verified before dispatch; plan completion judged by all tasks terminal, never by the first.

## Branch: List outstanding instructions

Scan `~/.straw-boss/dispatch/` (excluding `archive/`), report grouped by status. Pure read.

## Branch: Wrap up an instruction

1. Confirm which instruction (ask if ambiguous).
2. If `herdr-pane` and the pane/tab is still open and no longer needed, close it first (`herdr pane close`/`herdr tab close` — tab only if it was the last pane in it). `claude-p` has nothing to close.
3. Call `wrap-up-task.py` — sets `wrapped-up`, archives the file, and for a plan task syncs `plan.json` to the terminal status read from that task's own status file (refuses if not yet `done`/`failed`). Never `mv`/`Edit` this by hand.

**Verification:** pane/tab confirmed closed before the file is archived, never assumed.

## Red Flags

- "No herdr session available, ask the user to open one anyway" — last resort only; default to `claude-p` first.
- "Skip writing the instruction until dispatch succeeds" — no, write it `pending` first; a stray pending file on failure is signal, not noise.
- "Reconstruct the herdr command sequence from memory" — no, always the reference.
- "This worker's mode doesn't matter, use whatever's default" — no, mirror the orchestrator's actual mode every time.
- "Pane looks closed already, skip confirming" — no, check via `herdr pane get`/`agent get` first.
- "Two unrelated dispatches, share a batch to save a tab" — no, batch is one multi-app unit of work only.
- "3 ready tasks, dispatch one at a time to keep it simple" — no, all at once, always.
- "This idle finished session could take the next ready task" — no, unless it's literally the same task's next phase.
- "First task in the plan finished, mark the plan done" — no, only once every task is terminal.
- "Task might need clarification but herdr's available, use claude-p to keep it simple" — no, herdr-pane is required in that case.
- "The task's mid-flight question, relay it like an authorization checkpoint" — no, `awaiting-user-input` is answered directly in the pane; a question the orchestrator can itself answer goes through `SendMessage` instead, not a status transition.
- "Skip the worktree verify-repair step, herdr worktree create usually works fine" — no, the `config.worktree` bug happens with *any* creation method on a repo with `extensions.worktreeConfig`; verify every time.
- "Dispatch the herdr-pane task first, worry about orchestrator addressability if a worker actually needs it" — no, Task 1 requires this checked *before* the first herdr-pane dispatch this session; a worker that needs the channel and finds it unaddressed doesn't get an error, it gets silent misdelivery to an unrelated session.
- "This coordination question sounds like something the orchestrator could reasonably weigh in on, SendMessage it" — no, per `cross-session-coordination.md`: any trade-off or "which direction" call is `awaiting-user-input`, full stop, regardless of how qualified the orchestrator seems.
