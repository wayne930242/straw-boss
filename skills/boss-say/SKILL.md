---
name: boss-say
description: Route work through Straw Boss. Use for one task, a small independent batch, or a backlog; select the owning skill, the lightest sufficient execution tier, and the coordination graph.
---

## Overview

This skill owns routing and capped-batch scheduling. Domain work stays with its specialist: `shipping-task`, `inspecting-app`, `investigating-app`, or `troubleshooting-app`. `work-on` resolves the app; `dispatching-work` supplies mechanics only when a separate workroom is useful.

Choose the **smallest sufficient execution tier**. The process is light when its coordination cost stays below the work it coordinates. Once work is dispatched, the user and dispatched agent choose the specification, design, implementation, and the verification method inside the named reality anchor.

## Branch: Receiving an orchestrator handoff

When the incoming prompt names an `Orchestrator handoff file`, read that offered
continuity record and route its single transferred scope through Task 1. After
the owner, coordination graph, and reality anchor are established, record
acceptance from this receiving pane before implementation continues:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/accept-orchestrator-handoff.py" \
  --handoff-path <path> --owner <owning-skill> \
  --coordination-graph '<graph>' --reality-anchor '<anchor>'
```

Those structured route facts are the acceptance record. Use the owner,
graph, and anchor actually established in Task 1; the source validates all
three before transferring ownership.

The source already obtained approval for this window. Use the record's excluded
scopes as ownership boundaries; ask only a new work decision that
the routed task itself genuinely needs.

## Branch: A skill is named right after the trigger phrase

For `boss say <skill> <work>`, resolve a clear name, abbreviation, or partial match and invoke that skill with `<work>`. State a genuine ambiguity or missing match. A multi-item batch still follows the batch path below, using the named skill as each item's owner.

## Task 1: Triage scale and execution tier, then pick the dispatch shape

Collect the items, select the owning skill, and state the shape with one reason.

- **One bounded logical item:** the current agent carries a bounded single-loop end to end when it can load the target checkout's instructions. This includes implementation, inspection, investigation, and diagnosis.
- **Clear independent branches inside one item:** use sub-agent fan-out/fan-in and integrate the branches here.
- **A separate durable workroom is useful:** dispatch when the work benefits from its own interactive pane, long-lived checkpoint, continuation, or app ownership boundary.
- **Several app-rooted workers:** use orchestrator-worker. A small batch runs in this turn; a long backlog uses the self-paced batch path.

A bounded investigation may use a confirmed lower-tier work route and returns an explanatory, evidence-backed result.

Invoke `choosing-graph` and state the coordination graph and reality anchor. A capped batch is always orchestrator-worker. `single-loop` and `sub-agent fan-out/fan-in` create no `plan.json` and no repo-internal Straw Boss planning or spec document. When either uses a dispatched workroom, files under `~/.straw-boss/dispatch/` are the dispatch's lifecycle record, archived once the dispatch wraps up.

**Complete when:** the owner, graph, anchor, and execution tier are stated; a single item has no batch plan; batch work continues below.

## Task 2: Resolve each item's app

Batch path only (a single request left for `shipping-task` in Task 1 — nothing to do here).

For each item, extract a task description and, if the project has more than one app configured, resolve its target app via `work-on`'s Task 1 (its single-app fast path applies the same way here). Follow `dispatching-work` Task 3's brief boundary: resolve the app and coordination shape, but leave implementation/context investigation to the worker. Ask about a genuinely ambiguous item individually — don't interrogate every item just because a few are unclear.

**A batch item is never decomposed.** If resolving one item reveals it actually needs its own dependency graph (multiple phases, multiple apps for that one item), that item doesn't belong in this batch — pull it out per Task 1's mixed-input rule and route it through `shipping-task`.

**Verification:** every item in the batch has a task description and a resolved app; anything that turned out to need decomposition was pulled out and flagged, not folded in.

## Task 3: Decide the batch-wide mode default

Per resolved app, `forbidDirectCommit: true` forces team-mode for that item automatically — no question. For everything else, present **one** batch-wide solo-mode or team-mode decision through the harness-native ask-question interface. A mixed batch (some apps forced to team-mode, others taking the batch default) is expected and fine. This single answer is the only human checkpoint a solo-mode item in the batch ever gets — its commit itself needs no authorization, so Task 5 step 8's stalled-batch detection never fires for it.

**Verification:** the mode question was asked at most once per batch invocation, not once per item.

## Task 4: Write the batch as a plan

Derive the batch slug: a name the user gave the batch, or a slug from the source file's name if one was used, kebab-cased. This slug is load-bearing — it's how a later `/loop` tick finds this same batch again, so state it plainly in the confirmation and repeat it in a progress report only when needed to identify the batch.

Present the resolved item list, each one's app, the chosen mode default, and the batch slug as one plan-confirmation decision through the harness-native ask-question interface before writing anything — this commits to real dispatches next. Then write `~/.straw-boss/plans/<batch-slug>/plan.json` using `dispatching-work`'s own plan schema (`references/plan-mechanics.md`) exactly — every task's `depends_on: []`. Create the empty `status/` and `artifacts/` directories the same way `work-on`'s own Task 5 does. No `grilling` pass here — there's no dependency graph to confirm, only the flat item list from Task 2.

**Verification:** `plan.json` exists with one task per batch item, every `depends_on` empty, before any dispatch happens; the batch slug has been stated to the user.

## Task 5: Dispatch under a concurrency cap

Resolve the cap from the invocation or a documented project/provider policy.
When neither supplies one, use 4 as this plugin's scheduling fallback rather
than as a claim about provider capacity. Surface any runtime-contention-based
reduction to the user.

1. Compute in-flight count: every task whose plan status is `dispatched` and whose status file is not terminal (`done`/`failed`/`cancelled`) (`read-plan-status.py --in-flight`) — **not** `--not-done`, which also counts every still-`planned` task in the ready queue itself and overcounts in-flight by exactly that amount, silently starving the refill this whole task exists to do. This includes `awaiting-authorization`, `awaiting-user-input`, and `awaiting-main-agent` — their pane/worktree is still open, so they still hold a slot.
2. Compute the ready set (`read-plan-status.py --ready`).
3. **Slice** the ready set to `cap - in-flight`, dispatch only that slice — one task at a time through `dispatching-work`'s Tasks 1-5 (mode selection, instruction write, dispatch, confirm), never through its "Branch: Dispatch a plan" as a whole, since that branch's contract is "dispatch every ready task at once," which is exactly what the cap exists to prevent. The rest of the ready set stays queued for the next refill.
4. On a `done`/`failed`/`cancelled` status event for any in-flight task: receive the Herdr notification, auto-detach it, then refill the queue. `cancelled` is coordinator-authored only for an explicit user request or an objectively invalid dispatch, per `docs/roles.md`. A headless Claude `failed` note carrying a user-owned decision is the exception: reserve that freed slot and preserve its team-mode worktree, present the one decision, wrap only the dispatch record, then write a fresh-slug attempt carrying the answer and the same `repo_root` with `--retry-failed-plan-task`. That write removes the failed status and returns the plan task to `dispatched`; refill remaining capacity afterward.
5. `awaiting-authorization`/`awaiting-user-input` are not terminal and do not free a slot. Report the coordination delta compactly. For an interactive task, name it and point the user to its pane. For headless Codex, present its user-owned decision through the harness-native ask-question interface, one decision at a time, then resume the recorded thread with the answer.
6. `awaiting-main-agent` is also not terminal and does not free a slot. Resolve it in the same tick only with integrated context or a coordinator-owned action result: an interactive task uses `reply-to-worker.py --worker-instruction-path <path> --reply "<answer or action result>"`; headless Codex resumes its recorded thread. If it asks for a work-content decision, direct it to the user instead. Headless Claude reaches this need through step 4's terminal failed-and-retry path.
7. **A feature-branch push notification is not a plan-status event — it never appears in `read-plan-status.py` or `watch-plan-status.py`.** A team-mode task pushed its own feature branch and opened or updated an MR/PR on its own (`shipping-task`'s Task 3/Overview, unchanged for a batch item) — it needed no authorization and was never waiting. Relay the script-delivered FYI to the user; a task with no live route records it in the progress trail. Don't treat it as `awaiting-authorization`, obtain authorization, or change slot accounting.
8. **Idle in-flight tasks — peek on entry or change.** When every currently in-flight task first enters `awaiting-authorization`/`awaiting-user-input`, or one of those states or notes changes, invoke `peeking-work` on the changed task. Report that new finding by name. If in-flight also equals the cap, report the newly observed **fully stalled batch**. (`awaiting-main-agent` is resolved by step 6.)

**Don't re-peek or report unchanged idleness.** A later event or `/loop` tick carrying the same state and note is confirmation, not a coordination delta. Retain the prior finding and use quiet pacing until the task changes or the user asks.

**Verification:** in-flight count never exceeds the cap; a freed slot is refilled before anything else happens for that tick, except the slot reserved for a headless Claude decision retry; the plan branch's "whole ready wave at once" behavior was never invoked directly on the full batch; an `awaiting-main-agent` finding is resolved in the same tick through its interactive reply or headless Codex resume route; a feature-branch push notification is relayed to the user as an FYI whenever it arrives, never treated as `awaiting-authorization` and never held for a slot it was never holding; every idle in-flight task (`awaiting-authorization`/`awaiting-user-input` only) gets a `peeking-work` check once per stretch of idleness, not only once the batch is fully saturated at cap, and never repeatedly for the same unchanged state; a fully stalled batch is reported, not silently waited on.

## Task 6: Run the batch — one-shot, or self-paced

Which of these applies was already decided in Task 1. The one thing to check here is whether **this turn is itself a `/loop` tick**: it is only if the input this turn started with literally arrived as a `/loop` prompt carrying the batch slug. Anything else — a direct invocation, a plain mention of "boss-say" — is a fresh invocation, whatever Task 1 decided about pacing. Don't infer a tick from context or from the batch being large.

**One-shot batch:** drive the batch as far as it goes within this turn. Run `watch-plan-status.py --plan <slug>` as the authoritative scheduling stream and react to every persisted `done`/`failed`/`cancelled`/checkpoint revision per Task 5. The shared status command also prompts each recorded main-agent herdr pane after persistence; that live route accelerates observation but never replaces the watcher. Feature-branch push FYIs remain outside Plan status and are relayed per Task 5 step 7 whenever observed. Continue until either every task is terminal, or the turn has to stop and hand something back to the user. **Never call `ScheduleWakeup` in this shape** — there is no `/loop` iteration to schedule.

**Self-paced batch, first turn:** after Task 4 writes `plan.json`, dispatch the first fill per Task 5, then start the loop yourself — invoke the `loop` skill with the prompt `boss-say <batch-slug>` and no interval, so it runs in dynamic-pacing mode and each tick re-enters this skill with the slug. Tell the user the loop is running and how to stop it. Starting the loop is this skill's job; never end a turn having told the user to type `/loop` themselves.

**Self-paced batch, on a tick:** don't start a new batch — use the batch slug carried in the wake-up prompt to find and read the existing `plan.json` and `status/` for the batch already in progress; never guess the slug and never start a second `plan.json` for what might be the same batch. Run one round of Task 5. A new or changed idle finding from step 8 is news and sets `noop: false`; unchanged idleness stays quiet. A relayed push notification or resolved `awaiting-main-agent` checkpoint also counts as change. Otherwise call `ScheduleWakeup` with the same slug and `noop: true`. Once every task is terminal, report the final summary and call `ScheduleWakeup({stop: true})`.

**Verification:** `ScheduleWakeup` is called only on a confirmed `/loop` tick, every prompt carries the batch slug, and no tick starts a duplicate plan. A newly observed stall is reported once; its unchanged later ticks are quiet.

## Task 7: Wrap up

Once every task in the plan is terminal, report a summary: how many `done`, how many `failed` and why (from each failed task's status-file `note`), and how many `cancelled` and why (from each cancelled task's own note — the main agent's own reason for ending it). This is the same completion condition `dispatching-work`'s own plan branch uses — judged across all tasks, never on the first one finishing. Stop the status watcher (one-shot) or send the final `ScheduleWakeup({stop: true})` (self-paced) as the last step, not an afterthought.

For each item that landed a programming change, confirm its completion reference and record the single review disposition defined by `choosing-graph`.

**Verification:** every task is terminal and summarized; each changed item has one confirmed completion reference and one review disposition.

## Branch: Status query, or closing out one dispatch

Not new triage — "what's currently running", or "close out `<task>`" for a single dispatched instruction, is a passthrough to `dispatching-work`'s own List / Wrap-up branches (not this skill's Task 7, which is about reporting a *batch* this skill itself started). Invoke `dispatching-work` directly for the read or the close-out; don't reimplement the scan or the confirm-then-archive steps here.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/plan-mechanics.md` — plan/status file schemas, watcher command, authorization/user-input checkpoint handling — all reused as-is.
- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/dispatch-mechanics.md` — single-task dispatch mechanics used per sliced item.
- `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md` — `forbidDirectCommit` field used in Task 3.
