---
name: boss-say
description: Use when the user hands over many separate, independent work items at once — "work through this backlog", "fix these N tickets", "boss-say <list/file>" — either as a single long-running turn or repeatedly via `/loop`. Not for one task (`shipping-task`) or one request that decomposes into a dependency graph (`work-on`'s own Plan mechanism).
---

## Overview

A batch is a `dispatching-work` plan where every task's `depends_on` is empty — every item is independent and ready from the start. That means the entire batch would otherwise dispatch as a single wave (`dispatching-work`'s own rule: dispatch every ready task at once). For a batch of any real size that's too much at once — this skill's whole reason to exist is slicing that wave under a concurrency cap and refilling as items finish, everything else reuses `dispatching-work`'s existing per-task mechanics unmodified.

## Task 1: Resolve the batch

Get the list of items from wherever the caller pointed: inline in the invocation, or a file (checklist, tracker export) named in it. For each item, extract a task description and, if the project has more than one app configured, resolve its target app via `work-on`'s Task 1 (its single-app fast path applies the same way here). Ask about a genuinely ambiguous item individually — don't interrogate every item just because a few are unclear.

**A batch item is never decomposed.** If resolving one item reveals it actually needs its own dependency graph (multiple phases, multiple apps for that one item), that item doesn't belong in this batch — tell the user and suggest running it through `shipping-task` normally instead, outside boss-say.

**Verification:** every item in the batch has a task description and a resolved app; anything that turned out to need decomposition was pulled out and flagged, not folded in.

## Task 2: Decide the batch-wide flow default

Per resolved app, `forbidDirectCommit: true` forces the full flow for that item automatically — no question. For everything else, ask **once** for the whole batch — light flow or full flow default — never per item; fifty identical prompts is a defect, not thoroughness. A mixed batch (some apps forced to full flow, others taking the batch default) is expected and fine.

**Verification:** the flow question was asked at most once per batch invocation, not once per item.

## Task 3: Write the batch as a plan

Derive the batch slug: a name the user gave the batch, or a slug from the source file's name if one was used, kebab-cased. This slug is load-bearing — it's how a later `/loop` tick finds this same batch again, so state it plainly in the confirmation and every progress report from here on.

Confirm the resolved item list, each one's app, the chosen flow default, and the batch slug with the user before writing anything — this commits to real dispatches next. Then write `~/.straw-boss/plans/<batch-slug>/plan.json` using `dispatching-work`'s own plan schema (`references/plan-mechanics.md`) exactly — every task's `depends_on: []`. Create the empty `status/` and `artifacts/` directories the same way `work-on`'s own Task 5 does. No `grilling` pass here — there's no dependency graph to confirm, only the flat item list from Task 1.

**Verification:** `plan.json` exists with one task per batch item, every `depends_on` empty, before any dispatch happens; the batch slug has been stated to the user.

## Task 4: Dispatch under a concurrency cap

Default cap: 4 in-flight at once. The caller may set a different cap explicitly at invocation; if machine load looks like an issue mid-batch, lowering it for the rest of the batch is a judgment call to surface to the user, not something to change silently.

1. Compute in-flight count: every task whose plan status is `dispatched` and whose status file is not `done`/`failed` (`read-plan-status.py --not-done`). This includes `awaiting-authorization` and `awaiting-user-input` — their pane/worktree is still open, so they still hold a slot.
2. Compute the ready set (`read-plan-status.py --ready`).
3. **Slice** the ready set to `cap - in-flight`, dispatch only that slice — one task at a time through `dispatching-work`'s Tasks 1-5 (mode selection, instruction write, dispatch, confirm), never through its "Branch: Dispatch a plan" as a whole, since that branch's contract is "dispatch every ready task at once," which is exactly what the cap exists to prevent. The rest of the ready set stays queued for the next refill.
4. On a `done`/`failed` notification for any in-flight task: auto-detach it (same rules as `dispatching-work`'s plan branch — close its pane/tab if `herdr-pane`, remove its worktree if full-flow, call `wrap-up-task.py`), then repeat from step 1 — a freed slot gets backfilled from the queue immediately, not batched up for later.
5. `awaiting-authorization`/`awaiting-user-input` are not terminal and do not free a slot — report them the same way `dispatching-work`'s plan branch does (name the task, point at where to authorize or answer it), then leave them alone.
6. **Stalled batch:** if in-flight equals the cap and every one of those in-flight tasks is `awaiting-authorization`/`awaiting-user-input` — nothing can be dispatched and nothing will free a slot without the user — say so explicitly: name every stalled task and what each is waiting on. This is not a quiet tick; always surface it (see Task 5's `/loop` handling).

**Verification:** in-flight count never exceeds the cap; a freed slot is refilled before anything else happens for that tick; the plan branch's "whole ready wave at once" behavior was never invoked directly on the full batch; a fully-stalled batch is reported, not silently waited on.

## Task 5: One-shot vs. `/loop` invocation

**Detecting the mode:** you are in `/loop` mode only when this turn's invocation literally arrived as a `/loop` prompt (the input the turn started with names `/loop`, carrying the batch slug — see below). Anything else — a direct call to this skill, a plain mention of "boss-say" — is one-shot. Don't infer `/loop` mode from context or from the batch being large; check what actually invoked this turn.

**One-shot** (the default): drive the batch as far as it goes within this turn. Use a real `Monitor` polling loop over the plan's `status/` directory (exact command in `plan-mechanics.md`) to detect `done`/`failed`/`awaiting-authorization`/`awaiting-user-input` events and react per Task 4. Continue until either every task is terminal, or the turn has to stop and hand something back to the user (an authorization or a question, including a fully stalled batch per Task 4 step 6). **Never call `ScheduleWakeup` in this mode** — there is no `/loop` iteration to schedule.

**`/loop` mode:** the first time you enter this mode for a batch, after Task 3 writes `plan.json`, call `ScheduleWakeup` with a `prompt` that names this skill and includes the batch slug (e.g. `boss-say <batch-slug>`) — that's what makes the next tick resumable. On every tick after that: don't start a new batch — use the batch slug carried in the wake-up prompt to find and read the existing `plan.json` and `status/` for the batch already in progress; never guess the slug and never start a second `plan.json` for what might be the same batch. Run one round of Task 4 (refill up to the cap from whatever's ready). If Task 4 found a fully stalled batch, report it plainly and set `noop: false` — a stall is news, not quiet. Otherwise call `ScheduleWakeup` (same batch-slug prompt) to self-pace the next tick — `noop: true` only if nothing changed this tick (no new dispatch, no new terminal state, no new stall), `noop: false` otherwise. Once every task in the plan is terminal, report the final summary and call `ScheduleWakeup({stop: true})` — don't leave the loop running once the batch is actually done.

**Verification:** `ScheduleWakeup` is called only when this invocation is confirmed to be a `/loop` iteration (per the detection rule above), never in a one-shot call; every `ScheduleWakeup` prompt carries the batch slug; a `/loop` tick that starts a second, duplicate `plan.json` for the same batch is a defect — always resume the existing one; a fully stalled batch is never reported as a quiet `noop: true` tick.

## Task 6: Wrap up

Once every task in the plan is terminal, report a summary: how many `done`, how many `failed` and why (from each failed task's status-file `note`). This is the same completion condition `dispatching-work`'s own plan branch uses — judged across all tasks, never on the first one finishing. Stop the `Monitor` (one-shot) or send the final `ScheduleWakeup({stop: true})` (`/loop` mode) as the last step, not an afterthought.

**Verification:** the batch is reported complete only once every task's status is `done` or `failed`, never earlier.

## Red Flags

- "20 independent items, hand the whole ready wave to `dispatching-work`'s plan branch like normal" — no, that branch dispatches everything at once; boss-say exists specifically to slice it under the cap instead.
- "Ask each item whether it wants light or full flow, to be thorough" — no, Task 2: once for the whole batch, `forbidDirectCommit` items excepted.
- "This item actually needs its own dependency graph, just add depends_on edges into the batch plan" — no, a batch item is never allowed to depend on another; pull it out and route it through `shipping-task` instead.
- "Finished this tick, call `ScheduleWakeup` to check again later" when this was a plain one-shot call — no, `ScheduleWakeup` only applies to an actual `/loop` iteration; a one-shot call uses `Monitor` within the same turn instead.
- "A `/loop` tick came back and the batch plan already exists, just start a fresh one to be safe" — no, always resume the existing `plan.json` for that batch slug.
- "One item finished, wait for a few more before dispatching the next queued one" — no, Task 4: refill immediately, every time a slot frees.
- "Report the batch done once most items finished" — no, Task 6: every task terminal, not most.
- "All slots are stuck on authorization and nothing changed, mark this tick `noop: true` and stay quiet" — no, Task 4 step 6: a fully stalled batch is always surfaced, `noop: false`, naming what's waiting on the user.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/plan-mechanics.md` — plan/status file schemas, Monitor command, authorization/user-input checkpoint handling — all reused as-is.
- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/dispatch-mechanics.md` — single-task dispatch mechanics used per sliced item.
- `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md` — `forbidDirectCommit` field used in Task 2.
