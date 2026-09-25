---
name: boss-say
description: Use when the user or prompt explicitly names boss say, or when work spans multiple managed apps.
---

## Route the work

Select the owning skill, resolve the target through [work-on](../work-on/SKILL.md), and apply [choosing-graph](../choosing-graph/SKILL.md).
Load the owning skill when this session carries the work; a dispatched worker chooses its own method in its checkout.
Carry bounded work here; use a separate workroom when app ownership, interaction, or continuity warrants one.
Source-changing work follows the target's source-change workflow and [shipping-task](../shipping-task/SKILL.md).

For `boss say <skill> <work>`, invoke the matching skill with the work.
Ask only when the name is ambiguous.
A status query goes directly to [dispatching-work](../dispatching-work/SKILL.md#recover-and-hand-off).

## Receive an orchestrator handoff

A handoff arrives as a prompt carrying a handoff ID and summary; `dispatch_control` has already moved the listed dispatches to this session.
Route the summary's scope above, carrying its existing approval and scope exclusions.
Recreate its undispatched tasks and dependencies as todo items, and read the moved dispatches with `dispatch_control` roll-call.

## Plan and schedule

This skill owns task decomposition, dependency edges, and scheduling.
Reuse the user's specified tasks and decisions; ask only about an unresolved scope or dependency choice.
A task is the largest item one worker can own end to end in one resolved app.
A dependency carries the prerequisite's exact artifact path in both briefs when output is required.

Every task is a todo item, and an undispatched task's item names the tasks it depends on.
Name each task's anchor here, which settles [where its checkpoint runs](../choosing-graph/SKILL.md#reality-anchors).
Every group whose checkpoint is shared gets one checkpoint task depending on the tasks it covers, and those tasks dispatch with their checkpoint marked shared.
A checkpoint task becomes ready when every covered task is `delivered`: its result satisfies [Wrap up](../dispatching-work/SKILL.md#wrap-up) item 1 and it waits only on this checkpoint.
Correctness and contract findings return as fix tasks, and each covered change-set takes its [disposition](../choosing-graph/SKILL.md#review-checkpoint) from that one result.
Resolve source-changing items' lifecycle modes through [Select the mode](../shipping-task/SKILL.md#select-the-mode), reusing a batch-wide answer where applicable.

Use the invocation's concurrency cap or documented project policy; otherwise use 4.
Reduce it for observed contention and report the reason.
Incompatible shared-checkout writers remain queued.

On entry and each delivered event:

1. Handle it through [dispatching-work](../dispatching-work/SKILL.md#handle-events).
2. Launch at most `cap - in-flight` ready tasks in the same turn through [dispatching-work](../dispatching-work/SKILL.md#launch-a-dispatch). A worker waiting on a user decision still holds its slot.
3. Report the coordination delta. If every in-flight task is waiting, identify the blocker and next event.

A failed or cancelled prerequisite leaves its dependents blocked.
Report the blocked tasks and resolve their next action with the user; only `done` satisfies a dependency, except that `delivered` satisfies a checkpoint task's dependency on the tasks it covers.
A retry gets a fresh dispatch.

**Complete when:** every item is terminal and cleaned up, or has a recorded blocker and next event.
Report outcomes across the whole round through [reporting-to-user](../reporting-to-user/SKILL.md).
