---
name: boss-say
description: The single entry point for handing any work to straw-boss — implementation, audit, research, diagnosis, or anything else this session already has an available skill for. Use whenever the user hands work over or asks for something to be looked into — one item, a handful, or a whole backlog — e.g. "boss say <...>", "work on this", "implement X in <app>", "audit this module", "how does X work here", "X is failing", "work through this backlog". This skill judges the scale and, per item, the execution tier (a plain subagent, or a dispatched agent rooted in the app) and picks the dispatch shape (one item via a specialist skill or a better-fitting available skill, a capped batch in this turn, or a self-paced `/loop` batch).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework the main agent acts under — not redefined here.

**Everything comes through here — not just implementation.** The main agent decides dispatch shape and execution tier; once launched, the dispatched agent decides implementation with the user. `shipping-task` (implementation's git lifecycle), `inspecting-app`/`investigating-app`/`troubleshooting-app` (audit, research, diagnosis), `work-on` (app resolution), and `dispatching-work` (agent mechanics) are the machinery this skill drives; they're still invocable directly when the user names one — including right after the trigger phrase itself (see the branch below) — but they are not the front door.

Three things this skill owns that nothing else does:

1. **Scale triage** (Task 1) — one item, a batch that fits this turn, or a batch big enough to self-pace across turns.
2. **Execution-tier triage** (Task 1) — per item, whether it needs the target app's own real working directory at all. If not, a plain subagent handles it — no app-dir rooting, `dispatching-work` never involved. If it does, it's a dispatched agent — `dispatching-work` picks the actual transport itself (herdr-pane whenever available, `claude-p` only as an environment fallback; see its own Task 1 — that choice is never made here).
3. **Batch dispatch under a concurrency cap** (Tasks 4-6) — a batch is a `dispatching-work` plan where every task's `depends_on` is empty, so `dispatching-work`'s own rule ("dispatch every ready task at once") would fire the whole thing in one wave. Slicing that wave under a cap and refilling as items finish is this skill's reason to exist; everything else reuses `dispatching-work`'s per-task mechanics unmodified.

No type of work is excluded here: an audit, open-ended research, or an unexplained failure comes through this skill exactly like implementation does, judged by the same scale and execution-tier questions. The specialist skills (`inspecting-app`, `investigating-app`, `troubleshooting-app`) still own their own domain methodology — what this skill decides is whether an item goes solo or gets dispatched, not how the work itself gets done.

## Branch: A skill is named right after the trigger phrase

`boss say <slug> <rest>` — when the token right after the trigger phrase plausibly names a skill available this session, the user has already made the routing call themselves. Resolve it the same way the main agent already picks any skill — by name, a recognizable abbreviation, or an unambiguous partial match against the current skill listing (this plugin's own specialist skills, any other project skill, a user-level skill, or a plugin skill) — never by requiring a literal, character-for-character match. `ttt:work-on` resolving to `team-toon-tack:ttt-work-on` (an informally-typed plugin-name abbreviation over the skill's own base name) is exactly the kind of match this is meant to catch, not reject on a technicality. Hand off directly — `Skill({skill: <resolved-name>, args: <rest>})` — with the remainder of the invocation as its input, and skip Task 1's classification for it. This is not limited to the four specialist skills this plugin owns; any named, available skill qualifies, and the hand-off is unconditional once a skill is genuinely picked — never re-litigate whether it was the "right" choice once you've committed to it.

**Whether the dispatch machinery still applies depends on where the named skill's work actually lands, not on how it was invoked** — Task 1's execution-tier bullets below apply unchanged: work that stays outside any app's checkout runs solo, right here, exactly like this branch's hand-off; work that lands inside an app's checkout still needs Task 1's execution-tier call first (resolve the app via `work-on`, then decide solo-vs-dispatched) — naming the skill explicitly doesn't skip that gate.

Three exceptions:

- **No available skill is a plausible match.** Not "the token doesn't literally match a name" — only when, using genuine judgment (name, abbreviation, or the skill's own description), nothing in the current listing plausibly corresponds to what was named. Say so before falling through ("no skill matching `<slug>` here — treating it as part of the task") rather than silently absorbing it into the task text, then run Task 1 as normal.
- **More than one skill is a plausible match.** State which one you picked and why, in one line, before handing off — don't silently guess between them. If the ambiguity is genuine (no clearly better fit), ask instead of picking.
- **The named skill's work lands inside an app's checkout, but the input is actually a multi-item batch.** This branch is a single hand-off; a batch whose items land inside app checkouts still needs Task 1's scale triage and Tasks 4-6's dispatch-under-cap machinery, which no single skill owns on its own. Run Task 1 as normal, using the named skill as every item's type instead of judging it per item.

**Verification:** an available skill named right after the trigger is always resolved via judgment, never demanding a literal string match; a hand-off whose work lands inside an app's checkout still goes through Task 1's execution-tier call; ambiguity between two or more plausible skills is stated, never silently guessed; a genuinely unresolvable reference is called out, not quietly absorbed into the task text; a genuine batch still gets Task 1-6's machinery even when a specialist skill was named.

## Task 1: Triage scale and execution tier, then pick the dispatch shape

First collect the work items: inline in the invocation, or from a file (checklist, tracker export) named in it. Then decide the shape — **this is the main agent's call, made and stated, not a question put to the user.** The user may override after hearing it; don't ask them to choose up front.

- **One logical item** — a single task, or one request that decomposes into phases or spans several apps but is still one unit of work → route it to whichever skill actually owns its domain, main agent's own pick, stated with the reason: the matching specialist skill (`shipping-task` for implementation, `inspecting-app`/`investigating-app`/`troubleshooting-app` for audit/research/diagnosis) by default, or a better-fitting available skill this session already has for it (a tracker-integration task, for instance) when one clearly exists — whether or not the user named it. Then stop here. The chosen skill owns its own domain methodology and the dispatch; when its work lands inside an app's checkout, that also includes `work-on` (with its own Plan mechanism for a multi-phase request) and the execution-tier call below — see the slug branch above for the same "where the work lands" rule. Do not write a batch plan for a single item.
- **Several independent items, and the batch plausibly finishes inside this turn** — roughly the concurrency cap or a small multiple of it, each item short → **one-shot batch** (Task 6, status-watcher-driven).
- **A batch clearly bigger or longer than one turn** — many items, or items long enough that in-flight slots will keep turning over for a while → **self-paced batch**: this skill starts the `/loop` itself (Task 6), it does not tell the user to type `/loop` and come back.
- **Mixed input** — a backlog that also contains one item needing its own dependency graph: the batch items stay here, that item comes out and goes through the matching specialist skill separately. Say which item you pulled out and why.

State the chosen shape and the reason in one line before doing anything else.

**Then, per item, decide the execution tier — also the main agent's call, not the user's, and not a per-skill-type default:**

- **Doesn't need the target app's own real working directory** — a self-contained question, a lookup, something a plain capable agent can just do without being rooted in the app's own directory → a plain subagent (this session's own `Agent` tool). No app-dir rooting, `dispatching-work` never invoked.
- **Needs the app's real working directory** — real code changes, an audit against the app's real rule source, research into its actual current behavior, diagnosis using its own logs/tests → a dispatched agent via `dispatching-work`, which picks the transport itself (its own Task 1) and, independently, the agent kind (`dispatching-work`'s own agent-kind resolution — `claude` by default, which is also what makes the app's own skills/hooks/rules load; a differently-configured kind works from the task instruction and the app's own conventions instead, without that harness, per `docs/roles.md`).

This call is made by task type never having a fixed answer — an audit or a piece of research is not automatically "stays solo" any more than a code change is automatically "always dispatch." Judge the actual item.

**The only real mistake here is underestimating an item's complexity and going solo — in this session, without the app's own working directory — on something that actually needed a dispatched agent.** Second-guessing a call that turned out fine either way is not the point: dispatching something that turns out trivial, or keeping something solo that turns out to need more digging than expected, are not defects. Going solo on something that needed the app's own working directory is the one thing that costs something.

**Verification:** the shape was decided here and stated out loud, with a reason; a single item was never turned into a batch plan; the user was not asked to pick the dispatch shape or the execution tier; the execution tier was judged per item, not defaulted from the item's type.

## Task 2: Resolve each item's app

Batch path only (a single request left for `shipping-task` in Task 1 — nothing to do here).

For each item, extract a task description and, if the project has more than one app configured, resolve its target app via `work-on`'s Task 1 (its single-app fast path applies the same way here). Ask about a genuinely ambiguous item individually — don't interrogate every item just because a few are unclear.

**A batch item is never decomposed.** If resolving one item reveals it actually needs its own dependency graph (multiple phases, multiple apps for that one item), that item doesn't belong in this batch — pull it out per Task 1's mixed-input rule and route it through `shipping-task`.

**Verification:** every item in the batch has a task description and a resolved app; anything that turned out to need decomposition was pulled out and flagged, not folded in.

## Task 3: Decide the batch-wide flow default

Per resolved app, `forbidDirectCommit: true` forces the full flow for that item automatically — no question. For everything else, ask **once** for the whole batch — light flow or full flow default — never per item; fifty identical prompts is a defect, not thoroughness. A mixed batch (some apps forced to full flow, others taking the batch default) is expected and fine. This single answer is the only human checkpoint a light-flow item in the batch ever gets — its commit itself needs no authorization, so Task 5 step 8's stalled-batch detection never fires for it.

**Verification:** the flow question was asked at most once per batch invocation, not once per item.

## Task 4: Write the batch as a plan

Derive the batch slug: a name the user gave the batch, or a slug from the source file's name if one was used, kebab-cased. This slug is load-bearing — it's how a later `/loop` tick finds this same batch again, so state it plainly in the confirmation and every progress report from here on.

Confirm the resolved item list, each one's app, the chosen flow default, and the batch slug with the user before writing anything — this commits to real dispatches next. Then write `~/.straw-boss/plans/<batch-slug>/plan.json` using `dispatching-work`'s own plan schema (`references/plan-mechanics.md`) exactly — every task's `depends_on: []`. Create the empty `status/` and `artifacts/` directories the same way `work-on`'s own Task 5 does. No `grilling` pass here — there's no dependency graph to confirm, only the flat item list from Task 2.

**Verification:** `plan.json` exists with one task per batch item, every `depends_on` empty, before any dispatch happens; the batch slug has been stated to the user.

## Task 5: Dispatch under a concurrency cap

Default cap: 4 in-flight at once. The caller may set a different cap explicitly at invocation; if machine load looks like an issue mid-batch, lowering it for the rest of the batch is a judgment call to surface to the user, not something to change silently.

1. Compute in-flight count: every task whose plan status is `dispatched` and whose status file is not terminal (`done`/`failed`/`cancelled`) (`read-plan-status.py --in-flight`) — **not** `--not-done`, which also counts every still-`planned` task in the ready queue itself and overcounts in-flight by exactly that amount, silently starving the refill this whole task exists to do. This includes `awaiting-authorization`, `awaiting-user-input`, and `awaiting-main-agent` — their pane/worktree is still open, so they still hold a slot.
2. Compute the ready set (`read-plan-status.py --ready`).
3. **Slice** the ready set to `cap - in-flight`, dispatch only that slice — one task at a time through `dispatching-work`'s Tasks 1-5 (mode selection, instruction write, dispatch, confirm), never through its "Branch: Dispatch a plan" as a whole, since that branch's contract is "dispatch every ready task at once," which is exactly what the cap exists to prevent. The rest of the ready set stays queued for the next refill.
4. On a `done`/`failed`/`cancelled` status event for any in-flight task: receive the Herdr notification, auto-detach it, then refill the queue. `cancelled` is coordinator-authored only for an explicit user request or an objectively invalid dispatch, per `docs/roles.md`.
5. `awaiting-authorization`/`awaiting-user-input` are not terminal and do not free a slot — report them the same way `dispatching-work`'s plan branch does (name the task, point at where to authorize or answer it), then leave them alone.
6. `awaiting-main-agent` is also not terminal and does not free a slot. Resolve it in the same tick only with integrated context or a coordinator-owned action result: `reply-to-worker.py --worker-instruction-path <path> --reply "<answer or action result>"`. If it asks for a work-content decision, direct it to the user instead.
7. **A feature-branch push notification is not a plan-status event — it never appears in `read-plan-status.py` or `watch-plan-status.py`.** A full-flow task pushed its own feature branch and opened or updated an MR/PR on its own (`shipping-task`'s Task 3/Overview, unchanged for a batch item) — it needed no authorization and was never waiting. Relay the script-delivered FYI to the user; a task with no live route records it in the progress trail. Don't treat it as `awaiting-authorization`, obtain authorization, or change slot accounting.
8. **Idle in-flight tasks — peek, don't just trust the note.** Whenever every currently in-flight task is `awaiting-authorization`/`awaiting-user-input` — not only once in-flight reaches the cap — proactively invoke `peeking-work` on each one rather than waiting for its status file's `note` to fall short first. A static note can't tell "genuinely still waiting on the user" apart from "went silent — pane died, connection dropped, whatever — without ever reporting failure"; `peeking-work`'s live read can. Report every one by name and what the peek found. This is not a quiet tick; always surface it (see Task 6's `/loop` handling). If in-flight also equals the cap, call that out too — a **fully stalled batch**: nothing can be dispatched and nothing will free a slot without the user. (`awaiting-main-agent` never appears in this idle set — step 6 resolves it immediately, so it never sits waiting the way the other two wait on the user.)

**Don't re-peek a task that hasn't changed since its last peek.** Once a task has been peeked and reported, a later event carrying the exact same unchanged `awaiting-*` state and note is confirmation, not a fresh trigger — skip the peek and repeat the prior finding instead. Peek it again only when something about it actually changes (a new note, a status transition), or — self-paced batches only — on a later `/loop` tick; never tighten `ScheduleWakeup`'s own pacing just to check an idle task sooner. Within a single one-shot turn, this means each idle task gets peeked once per continuous stretch of idleness, not once per watcher event.

**Verification:** in-flight count never exceeds the cap; a freed slot is refilled before anything else happens for that tick; the plan branch's "whole ready wave at once" behavior was never invoked directly on the full batch; an `awaiting-main-agent` finding is resolved via `reply-to-worker.py` in the same tick it's detected, never left for a later peek; a feature-branch push notification is relayed to the user as an FYI whenever it arrives, never treated as `awaiting-authorization` and never held for a slot it was never holding; every idle in-flight task (`awaiting-authorization`/`awaiting-user-input` only) gets a `peeking-work` check once per stretch of idleness, not only once the batch is fully saturated at cap, and never repeatedly for the same unchanged state; a fully stalled batch is reported, not silently waited on.

## Task 6: Run the batch — one-shot, or self-paced

Which of these applies was already decided in Task 1. The one thing to check here is whether **this turn is itself a `/loop` tick**: it is only if the input this turn started with literally arrived as a `/loop` prompt carrying the batch slug. Anything else — a direct invocation, a plain mention of "boss-say" — is a fresh invocation, whatever Task 1 decided about pacing. Don't infer a tick from context or from the batch being large.

**One-shot batch:** drive the batch as far as it goes within this turn. Run `watch-plan-status.py --plan <slug>` as the authoritative scheduling stream and react to every persisted `done`/`failed`/`cancelled`/checkpoint revision per Task 5. The shared status command also prompts each recorded main-agent herdr pane after persistence; that live route accelerates observation but never replaces the watcher. Feature-branch push FYIs remain outside Plan status and are relayed per Task 5 step 7 whenever observed. Continue until either every task is terminal, or the turn has to stop and hand something back to the user. **Never call `ScheduleWakeup` in this shape** — there is no `/loop` iteration to schedule.

**Self-paced batch, first turn:** after Task 4 writes `plan.json`, dispatch the first fill per Task 5, then start the loop yourself — invoke the `loop` skill with the prompt `boss-say <batch-slug>` and no interval, so it runs in dynamic-pacing mode and each tick re-enters this skill with the slug. Tell the user the loop is running and how to stop it. Starting the loop is this skill's job; never end a turn having told the user to type `/loop` themselves.

**Self-paced batch, on a tick:** don't start a new batch — use the batch slug carried in the wake-up prompt to find and read the existing `plan.json` and `status/` for the batch already in progress; never guess the slug and never start a second `plan.json` for what might be the same batch. Run one round of Task 5 (refill up to the cap from whatever's ready, resolving any `awaiting-main-agent` finding inline per step 6, relaying any feature-branch push notification per step 7). If Task 5 step 8 found any idle in-flight tasks, report what the `peeking-work` check found and set `noop: false` — this is news, not quiet, whether or not the batch is fully stalled at cap. A relayed push notification (step 7) also counts as something changing this tick, same as resolving an `awaiting-main-agent` checkpoint does below. Otherwise call `ScheduleWakeup` (same batch-slug prompt) to pace the next tick — `noop: true` only if nothing changed this tick (no new dispatch, no new terminal state, no new stall — resolving an `awaiting-main-agent` checkpoint counts as something changing), `noop: false` otherwise. Once every task in the plan is terminal, report the final summary and call `ScheduleWakeup({stop: true})` — don't leave the loop running once the batch is actually done.

**Verification:** `ScheduleWakeup` is called only on a confirmed `/loop` tick (per the detection rule above), never in a one-shot batch or on the turn that starts the loop; every `ScheduleWakeup` prompt carries the batch slug; a tick that starts a second, duplicate `plan.json` for the same batch is a defect — always resume the existing one; a fully stalled batch is never reported as a quiet `noop: true` tick.

## Task 7: Wrap up

Once every task in the plan is terminal, report a summary: how many `done`, how many `failed` and why (from each failed task's status-file `note`), and how many `cancelled` and why (from each cancelled task's own note — the main agent's own reason for ending it). This is the same completion condition `dispatching-work`'s own plan branch uses — judged across all tasks, never on the first one finishing. Stop the status watcher (one-shot) or send the final `ScheduleWakeup({stop: true})` (self-paced) as the last step, not an afterthought.

**Verification:** the batch is reported complete only once every task's status is `done`, `failed`, or `cancelled`, never earlier; a `cancelled` task is counted and explained in the summary, not silently dropped from both the `done` and `failed` tallies.

## Branch: Status query, or closing out one dispatch

Not new triage — "what's currently running", or "close out `<task>`" for a single dispatched instruction, is a passthrough to `dispatching-work`'s own List / Wrap-up branches (not this skill's Task 7, which is about reporting a *batch* this skill itself started). Invoke `dispatching-work` directly for the read or the close-out; don't reimplement the scan or the confirm-then-archive steps here.

## Red Flags

- "The user only gave one task, so this skill doesn't apply — go straight to the specialist skill" — no, one item still comes through here; Task 1 routes it to the matching specialist skill after triage. Triage is what this skill is for.
- "Nothing matched a specialist, so run it through `shipping-task`/`inspecting-app` anyway" — no, Task 1: check first whether a better-fitting available skill already owns this item's actual domain (a tracker task, for instance) and hand off to it instead — the four specialists are the default for implementation/audit/research/diagnosis, not the only skills this triage can pick.
- "The token after the trigger phrase doesn't match a skill name character-for-character, treat it as task text" — no, the slug branch resolves by judgment (name, abbreviation, description), not literal equality; only fall through when no available skill is a plausible match at all.
- "This batch is too big for one turn, tell the user to run `/loop boss-say ...`" — no, Task 6: the main agent starts the loop itself.
- "Ask the user whether they want a one-shot run or a loop" — no, Task 1: the main agent decides the shape and states it; the user overrides if they disagree.
- "20 independent items, hand the whole ready wave to `dispatching-work`'s plan branch like normal" — no, that branch dispatches everything at once; the cap exists specifically to slice it.
- "Ask each item whether it wants light or full flow, to be thorough" — no, Task 3: once for the whole batch, `forbidDirectCommit` items excepted.
- "This item actually needs its own dependency graph, just add depends_on edges into the batch plan" — no, a batch item is never allowed to depend on another; pull it out and route it through the matching specialist skill instead.
- "Finished this tick, call `ScheduleWakeup` to check again later" when this was a one-shot batch — no, `ScheduleWakeup` belongs to an actual `/loop` tick; a one-shot batch keeps the status watcher running within the same turn instead.
- "A tick came back and the batch plan already exists, just start a fresh one to be safe" — no, always resume the existing `plan.json` for that batch slug.
- "One item finished, wait for a few more before dispatching the next queued one" — no, Task 5: refill immediately, every time a slot frees.
- "Report the batch done once most items finished" — no, Task 7: every task terminal, not most.
- "All slots are stuck on authorization and nothing changed, mark this tick `noop: true` and stay quiet" — no, Task 5 step 8: any tick where every in-flight task is idle is always surfaced, `noop: false`, naming what's waiting on the user and what `peeking-work` found — not only once the batch is fully stalled at cap.
- "Still idle, peek it again to be safe" on every repeated watcher event or `/loop` tick where nothing about the task actually changed — no, Task 5 step 8: peek once per stretch of idleness and repeat the prior finding for an unchanged state; re-peeking on every notification is an unbounded loop, not thoroughness.
- "A task is `awaiting-main-agent`, report it and leave it alone like the other two checkpoints" — no, Task 5 step 6: this one this skill resolves itself, immediately, via `reply-to-worker.py` — it never sits in the idle set step 8 peeks.
- "A task pushed its own feature branch, that's `awaiting-authorization`, report it and wait for the user to authorize" — no, Task 5 step 7: a feature-branch push needs no authorization; relay the FYI and move on, don't hold a slot for it or wait on the user.
- "The token after the trigger phrase looks like a slug but doesn't match anything loaded, just quietly treat it as part of the task" — no, the resolve-failure branch: say so first, then fall through to Task 1.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/plan-mechanics.md` — plan/status file schemas, watcher command, authorization/user-input checkpoint handling — all reused as-is.
- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/dispatch-mechanics.md` — single-task dispatch mechanics used per sliced item.
- `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md` — `forbidDirectCommit` field used in Task 3.
