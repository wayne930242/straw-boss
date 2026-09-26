---
name: boss-say
description: Use when the user or prompt explicitly names boss say, or when work spans multiple managed apps.
---

## Route the work

Select the owning skill, resolve the target through [resolving-app](../resolving-app/SKILL.md), and apply [choosing-graph](../choosing-graph/SKILL.md).
Carry bounded work here; use a separate workroom when app ownership, interaction, or continuity warrants one.
Source-changing work follows the target's `leveraging-tasks` route and [shipping-task](../shipping-task/SKILL.md).

For `boss say <skill> <work>`, invoke the matching skill with the work.
Ask only when the name is ambiguous.
A status query or single-dispatch close-out goes directly to [dispatching-work](../dispatching-work/SKILL.md#list-outstanding-dispatches).

## Receive an orchestrator handoff

Read the offered `Orchestrator handoff file` and route its transferred scope above.
After the owner, graph, and anchor are established, accept from this receiving pane:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/accept-orchestrator-handoff.py" \
  --handoff-path <path> --owner <owning-skill> \
  --coordination-graph '<graph>' --reality-anchor '<anchor>'
```

Use the established route facts.
Carry the existing approval and scope exclusions from the handoff record.
Acceptance moves the handoff's listed dispatches to this pane; coordinate its `transferred_dispatches` from here.

## Plan and schedule

This skill owns task decomposition, dependency edges, and scheduling.
Reuse the user's specified tasks and decisions; ask only about an unresolved scope or dependency choice.
A task is the largest item one worker can own end to end in one resolved app.
A dependency carries the prerequisite's exact artifact path in both briefs when output is required.

For multiple app-rooted workers, write `~/.straw-boss/plans/<slug>/plan.json` using [Plan file](../dispatching-work/references/plan-mechanics.md#plan-file), and create its `status/` and `artifacts/` directories.
Independent items have `depends_on: []`; dependent work uses the same plan with explicit edges.
Name each task's anchor here, which settles [where its checkpoint runs](../choosing-graph/SKILL.md#reality-anchors).
Every group whose checkpoint is shared gets one checkpoint task depending on the tasks it covers, and those tasks dispatch with their checkpoint marked shared.
Correctness and contract findings return as fix tasks in the same plan, and each covered change-set takes its [disposition](../choosing-graph/SKILL.md#review-checkpoint) from that one result.
State the slug and task summary.
Resolve source-changing items' lifecycle modes through [Select the mode](../shipping-task/SKILL.md#select-the-mode), reusing a batch-wide answer where applicable.

Use the invocation's concurrency cap or documented project/provider policy; otherwise use 4 as the scheduling fallback.
Reduce it for observed contention and report the reason.
Incompatible shared-checkout writers remain queued.

On entry and each persisted status revision:

1. Handle checkpoints through [dispatch events](../dispatching-work/SKILL.md#handle-events), and terminal tasks through [wrap-up](../dispatching-work/SKILL.md#wrap-up). Resolve a confirmed same-task continuation before cleanup.
2. Read `--in-flight` and `--ready` through [plan queries](../dispatching-work/references/plan-mechanics.md#read-plan-state). Launch at most `cap - in-flight` ready tasks, each through its lifecycle owner and `dispatching-work`. Pending user checkpoints still hold slots.
3. Report the coordination delta. If every in-flight task is waiting, identify the blocker and next event. Use [peeking-work](../peeking-work/SKILL.md) when the user asks or observed evidence disagrees with recorded state.

A failed or cancelled prerequisite leaves its dependents blocked.
Report the blocked tasks and resolve their next action with the user; only `done` satisfies a dependency.
A retry gets a fresh instruction through the normal launch path.

## Run or resume the plan

Use one [status watcher](../dispatching-work/references/plan-mechanics.md#monitor-plan-status) for a plan driven in this turn.
Persisted status is the scheduling authority; live Herdr notifications accelerate delivery.

For a self-paced backlog, use the harness's `loop` skill when available.
Start it with `boss-say <slug>` and dynamic pacing, then report how to stop it.
When that capability is absent, keep the persisted plan and name the supported continuation event.

A `/loop` tick resumes the existing slug, runs one scheduling round, then calls `ScheduleWakeup` with `noop: true` only when nothing changed.
Changed state uses `noop: false`; terminal completion uses `{stop: true}`.
These calls belong only to actual loop ticks.
Unchanged waiting stays quiet.

**Complete when:** every item is terminal and cleaned up, or has a recorded blocker and next event.
Report outcomes across the whole plan through [reporting-to-user](../reporting-to-user/SKILL.md); stop the watcher or loop when every task is terminal.
Review and completion references come from each lifecycle owner's result.
