---
name: shipping-task
description: Use to carry one task through a managed app's git lifecycle.
---

## Select the mode

Resolve an unknown target through [work-on](../work-on/SKILL.md).
Read `forbidDirectCommit` and `gitWorkflowSkill` from the [apps configuration](../../../skills/init/references/apps-config-schema.md).

Reuse the user's established mode and base branch.
Otherwise ask how the user regards this piece of work, with these consequences:

- **solo-mode:** work in the primary checkout and commit directly to the base branch.
- **team-mode:** worktree → develop → MR/PR → merge → archive.

`forbidDirectCommit: true` selects team-mode automatically.
For a batch, ask once for the remaining items' shared default.
Before solo work starts, check the primary checkout is clean and reserve it for one task at a time; resolve existing changes with their owner.

## Prepare and execute

The execution tier comes from [boss-say](../boss-say/SKILL.md#route-the-work).
In team-mode, the main agent creates and verifies the worktree and copies declared local files through [Prepare the checkout](../dispatching-work/SKILL.md#prepare-the-checkout).
The verified path becomes the worker's cwd.

The execution owner loads the target's instructions and uses its source-change workflow.
For post-worktree git operations, run `gitWorkflowSkill` when configured; otherwise commit the change, and in team-mode push the feature branch and open an MR/PR.
Separate workrooms use [dispatching-work](../dispatching-work/SKILL.md), including its worker contract.

## Mutation checkpoints

Apply existing user authorization to the specific action:

- Commits, pushes of the task's own feature branch, and its MR/PR creation continue within the authorized lifecycle. A dispatched worker reports a feature push in its final message.
- Merge and pushes to another tracked branch require user authorization. The current agent asks through `ask_user`; a dispatched worker without that authorization in its brief asks through `caller_ping` and stops until resumed.
- A monorepo pointer-bump push is a separate mutation whose authorization must cover that root repository.

Worker questions and continuation follow [Handle events](../dispatching-work/SKILL.md#handle-events).

## Complete the lifecycle

For each completed task, confirm its merge or commit reference.
A dispatched task invokes [wrap-up](../dispatching-work/SKILL.md#wrap-up), which resolves the [review checkpoint](../choosing-graph/SKILL.md#review-checkpoint) before cleanup.
Reuse a completed wrap-up result.
A current-agent task applies that checkpoint here.
Record one review disposition for the completed change-set.

A current-agent team-mode task removes its worktree with plain git; a dispatched task's worktree is removed in wrap-up.
If the primary checkout tracks the merged base, is clean, and is intended for subsequent direct work, fast-forward it using its established tracking configuration.
Update an originating tracker ticket once its lifecycle is complete.

**Complete when:** the completion reference and review are recorded, any dispatch is wrapped up, the worktree is removed, and the originating ticket reflects the result.
