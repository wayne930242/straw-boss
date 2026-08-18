---
name: boss-say
description: The single entry point for handing implementation work to straw-boss. Use whenever the user hands work over to be done — one task, a handful, or a whole backlog — e.g. "boss say <...>", "work on this", "implement X in <app>", "work through this backlog", "fix these N tickets". This skill judges the scale itself and picks the dispatch shape (one task via `shipping-task`, a capped batch in this turn, or a self-paced `/loop` batch). Not for read-only work (`inspecting-app`, `investigating-app`, `troubleshooting-app`).
---

## Overview

**Everything implementation-shaped comes through here.** The boss decides how work gets dispatched — the user hands over the work, not the dispatch shape. `shipping-task` (one task's git lifecycle), `work-on` (app resolution), and `dispatching-work` (agent mechanics) are the machinery this skill drives; they're still invocable directly when the user names one, but they are not the front door.

Two things this skill owns that nothing else does:

1. **Scale triage** (Task 1) — one task, a batch that fits this turn, or a batch big enough to self-pace across turns.
2. **Batch dispatch under a concurrency cap** (Tasks 4-6) — a batch is a `dispatching-work` plan where every task's `depends_on` is empty, so `dispatching-work`'s own rule ("dispatch every ready task at once") would fire the whole thing in one wave. Slicing that wave under a cap and refilling as items finish is this skill's reason to exist; everything else reuses `dispatching-work`'s per-task mechanics unmodified.

Read-only requests are not this skill's: an audit goes to `inspecting-app`, open-ended research to `investigating-app`, an unexplained failure to `troubleshooting-app` (which comes back here once it has a root cause).

## Task 1: Triage the scale, then pick the dispatch shape

First collect the work items: inline in the invocation, or from a file (checklist, tracker export) named in it. Then decide the shape — **this is the boss's call, made and stated, not a question put to the user.** The user may override after hearing it; don't ask them to choose up front.

- **One logical request** — a single task, or one request that decomposes into phases or spans several apps but is still one unit of work → invoke `shipping-task` and stop here. It owns the flow question, `work-on` (including `work-on`'s own Plan mechanism for a multi-phase request), and the dispatch. Do not write a batch plan for a single request.
- **Several independent items, and the batch plausibly finishes inside this turn** — roughly the concurrency cap or a small multiple of it, each item short → **one-shot batch** (Task 6, `Monitor`-driven).
- **A batch clearly bigger or longer than one turn** — many items, or items long enough that in-flight slots will keep turning over for a while → **self-paced batch**: this skill starts the `/loop` itself (Task 6), it does not tell the user to type `/loop` and come back.
- **Mixed input** — a backlog that also contains one item needing its own dependency graph: the batch items stay here, that item comes out and goes through `shipping-task` separately. Say which item you pulled out and why.

State the chosen shape and the reason in one line before doing anything else.

**Verification:** the shape was decided here and stated out loud, with a reason; a single request was never turned into a batch plan; the user was not asked to pick the dispatch shape.

## Task 2: Resolve each item's app

Batch path only (a single request left for `shipping-task` in Task 1 — nothing to do here).

For each item, extract a task description and, if the project has more than one app configured, resolve its target app via `work-on`'s Task 1 (its single-app fast path applies the same way here). Ask about a genuinely ambiguous item individually — don't interrogate every item just because a few are unclear.

**A batch item is never decomposed.** If resolving one item reveals it actually needs its own dependency graph (multiple phases, multiple apps for that one item), that item doesn't belong in this batch — pull it out per Task 1's mixed-input rule and route it through `shipping-task`.

**Verification:** every item in the batch has a task description and a resolved app; anything that turned out to need decomposition was pulled out and flagged, not folded in.

## Task 3: Decide the batch-wide flow default

Per resolved app, `forbidDirectCommit: true` forces the full flow for that item automatically — no question. For everything else, ask **once** for the whole batch — light flow or full flow default — never per item; fifty identical prompts is a defect, not thoroughness. A mixed batch (some apps forced to full flow, others taking the batch default) is expected and fine.

**Verification:** the flow question was asked at most once per batch invocation, not once per item.

## Task 4: Write the batch as a plan

Derive the batch slug: a name the user gave the batch, or a slug from the source file's name if one was used, kebab-cased. This slug is load-bearing — it's how a later `/loop` tick finds this same batch again, so state it plainly in the confirmation and every progress report from here on.

Confirm the resolved item list, each one's app, the chosen flow default, and the batch slug with the user before writing anything — this commits to real dispatches next. Then write `~/.straw-boss/plans/<batch-slug>/plan.json` using `dispatching-work`'s own plan schema (`references/plan-mechanics.md`) exactly — every task's `depends_on: []`. Create the empty `status/` and `artifacts/` directories the same way `work-on`'s own Task 5 does. No `grilling` pass here — there's no dependency graph to confirm, only the flat item list from Task 2.

**Verification:** `plan.json` exists with one task per batch item, every `depends_on` empty, before any dispatch happens; the batch slug has been stated to the user.

## Task 5: Dispatch under a concurrency cap

Default cap: 4 in-flight at once. The caller may set a different cap explicitly at invocation; if machine load looks like an issue mid-batch, lowering it for the rest of the batch is a judgment call to surface to the user, not something to change silently.

1. Compute in-flight count: every task whose plan status is `dispatched` and whose status file is not `done`/`failed` (`read-plan-status.py --in-flight`) — **not** `--not-done`, which also counts every still-`planned` task in the ready queue itself and overcounts in-flight by exactly that amount, silently starving the refill this whole task exists to do. This includes `awaiting-authorization` and `awaiting-user-input` — their pane/worktree is still open, so they still hold a slot.
2. Compute the ready set (`read-plan-status.py --ready`).
3. **Slice** the ready set to `cap - in-flight`, dispatch only that slice — one task at a time through `dispatching-work`'s Tasks 1-5 (mode selection, instruction write, dispatch, confirm), never through its "Branch: Dispatch a plan" as a whole, since that branch's contract is "dispatch every ready task at once," which is exactly what the cap exists to prevent. The rest of the ready set stays queued for the next refill.
4. On a `done`/`failed` notification for any in-flight task: auto-detach it (same rules as `dispatching-work`'s plan branch — close its pane/tab if `herdr-pane`, remove its worktree if full-flow, call `wrap-up-task.py`), then repeat from step 1 — a freed slot gets backfilled from the queue immediately, not batched up for later.
5. `awaiting-authorization`/`awaiting-user-input` are not terminal and do not free a slot — report them the same way `dispatching-work`'s plan branch does (name the task, point at where to authorize or answer it), then leave them alone.
6. **Stalled batch:** if in-flight equals the cap and every one of those in-flight tasks is `awaiting-authorization`/`awaiting-user-input` — nothing can be dispatched and nothing will free a slot without the user — say so explicitly: name every stalled task and what each is waiting on (from its status file's `note`; if that isn't enough to explain it, invoke `peeking-work` on that task rather than reading its pane/transcript inline here). This is not a quiet tick; always surface it (see Task 6's `/loop` handling).

**Verification:** in-flight count never exceeds the cap; a freed slot is refilled before anything else happens for that tick; the plan branch's "whole ready wave at once" behavior was never invoked directly on the full batch; a fully stalled batch is reported, not silently waited on.

## Task 6: Run the batch — one-shot, or self-paced

Which of these applies was already decided in Task 1. The one thing to check here is whether **this turn is itself a `/loop` tick**: it is only if the input this turn started with literally arrived as a `/loop` prompt carrying the batch slug. Anything else — a direct invocation, a plain mention of "boss-say" — is a fresh invocation, whatever Task 1 decided about pacing. Don't infer a tick from context or from the batch being large.

**One-shot batch:** drive the batch as far as it goes within this turn. Use a real `Monitor` polling loop over the plan's `status/` directory (exact command in `plan-mechanics.md`) to detect `done`/`failed`/`awaiting-authorization`/`awaiting-user-input` events and react per Task 5. Continue until either every task is terminal, or the turn has to stop and hand something back to the user (an authorization or a question, including a fully stalled batch per Task 5 step 6). **Never call `ScheduleWakeup` in this shape** — there is no `/loop` iteration to schedule.

**Self-paced batch, first turn:** after Task 4 writes `plan.json`, dispatch the first fill per Task 5, then start the loop yourself — invoke the `loop` skill with the prompt `boss-say <batch-slug>` and no interval, so it runs in dynamic-pacing mode and each tick re-enters this skill with the slug. Tell the user the loop is running and how to stop it. Starting the loop is this skill's job; never end a turn having told the user to type `/loop` themselves.

**Self-paced batch, on a tick:** don't start a new batch — use the batch slug carried in the wake-up prompt to find and read the existing `plan.json` and `status/` for the batch already in progress; never guess the slug and never start a second `plan.json` for what might be the same batch. Run one round of Task 5 (refill up to the cap from whatever's ready). If Task 5 found a fully stalled batch, report it plainly and set `noop: false` — a stall is news, not quiet. Otherwise call `ScheduleWakeup` (same batch-slug prompt) to pace the next tick — `noop: true` only if nothing changed this tick (no new dispatch, no new terminal state, no new stall), `noop: false` otherwise. Once every task in the plan is terminal, report the final summary and call `ScheduleWakeup({stop: true})` — don't leave the loop running once the batch is actually done.

**Verification:** `ScheduleWakeup` is called only on a confirmed `/loop` tick (per the detection rule above), never in a one-shot batch or on the turn that starts the loop; every `ScheduleWakeup` prompt carries the batch slug; a tick that starts a second, duplicate `plan.json` for the same batch is a defect — always resume the existing one; a fully stalled batch is never reported as a quiet `noop: true` tick.

## Task 7: Wrap up

Once every task in the plan is terminal, report a summary: how many `done`, how many `failed` and why (from each failed task's status-file `note`). This is the same completion condition `dispatching-work`'s own plan branch uses — judged across all tasks, never on the first one finishing. Stop the `Monitor` (one-shot) or send the final `ScheduleWakeup({stop: true})` (self-paced) as the last step, not an afterthought.

**Verification:** the batch is reported complete only once every task's status is `done` or `failed`, never earlier.

## Red Flags

- "The user only gave one task, so this skill doesn't apply — go straight to `shipping-task`" — no, one task still comes through here; Task 1 routes it to `shipping-task` after triage. Triage is what this skill is for.
- "This batch is too big for one turn, tell the user to run `/loop boss-say ...`" — no, Task 6: the boss starts the loop itself.
- "Ask the user whether they want a one-shot run or a loop" — no, Task 1: the boss decides the shape and states it; the user overrides if they disagree.
- "20 independent items, hand the whole ready wave to `dispatching-work`'s plan branch like normal" — no, that branch dispatches everything at once; the cap exists specifically to slice it.
- "Ask each item whether it wants light or full flow, to be thorough" — no, Task 3: once for the whole batch, `forbidDirectCommit` items excepted.
- "This item actually needs its own dependency graph, just add depends_on edges into the batch plan" — no, a batch item is never allowed to depend on another; pull it out and route it through `shipping-task` instead.
- "Finished this tick, call `ScheduleWakeup` to check again later" when this was a one-shot batch — no, `ScheduleWakeup` belongs to an actual `/loop` tick; a one-shot batch uses `Monitor` within the same turn instead.
- "A tick came back and the batch plan already exists, just start a fresh one to be safe" — no, always resume the existing `plan.json` for that batch slug.
- "One item finished, wait for a few more before dispatching the next queued one" — no, Task 5: refill immediately, every time a slot frees.
- "Report the batch done once most items finished" — no, Task 7: every task terminal, not most.
- "All slots are stuck on authorization and nothing changed, mark this tick `noop: true` and stay quiet" — no, Task 5 step 6: a fully stalled batch is always surfaced, `noop: false`, naming what's waiting on the user.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/plan-mechanics.md` — plan/status file schemas, Monitor command, authorization/user-input checkpoint handling — all reused as-is.
- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/dispatch-mechanics.md` — single-task dispatch mechanics used per sliced item.
- `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md` — `forbidDirectCommit` field used in Task 3.
