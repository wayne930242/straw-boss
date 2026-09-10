---
name: shipping-task
description: Use to carry one task through a managed app's git lifecycle.
---

## Select the mode

Resolve an unknown target through [work-on](../work-on/SKILL.md). Read `forbidDirectCommit` and `gitWorkflowSkill` from the [apps configuration](../init/references/apps-config-schema.md).

Reuse the user's established mode and base branch. Otherwise ask how the user regards this piece of work, with these consequences:

- **solo-mode:** work in the primary checkout and commit directly to the base branch.
- **team-mode:** worktree → develop → MR/PR → merge → archive.

`forbidDirectCommit: true` selects team-mode automatically. For a batch, ask once for the remaining items' shared default. Before solo work starts, check the primary checkout is clean and reserve it for one task at a time; resolve existing changes with their owner.

## Prepare and execute

The execution tier comes from [boss-say](../boss-say/SKILL.md#route-the-work). In team-mode, the main agent creates and verifies the worktree and copies declared local files through [Worktree ownership](../dispatching-work/references/plan-mechanics.md#worktree-ownership). The verified path becomes the worker's cwd.

The execution owner loads the target's instructions and uses its source-change workflow. For post-worktree git operations, run `gitWorkflowSkill` when configured; otherwise commit the change, and in team-mode push the feature branch and open an MR/PR. Separate workrooms use [dispatching-work](../dispatching-work/SKILL.md), including its brief contract.

## Mutation checkpoints

Apply existing user authorization to the specific action:

- Commits, pushes of the task's own feature branch, and its MR/PR creation continue within the authorized lifecycle. A dispatched worker reports a feature push through [notifying-main-agent](../notifying-main-agent/SKILL.md#report-a-feature-branch-push).
- Merge and pushes to another tracked branch require user authorization. The current agent asks locally; a dispatched worker asks in its own pane and reports `awaiting-authorization` while waiting.
- A monorepo pointer-bump push is a separate mutation whose authorization must cover that root repository.

Dispatch checkpoint transport and continuation follow [Handle events](../dispatching-work/SKILL.md#handle-events).

## Complete the lifecycle

For each completed task, confirm its merge or commit reference. A dispatched task invokes [wrap-up](../dispatching-work/SKILL.md#wrap-up), which resolves the [review checkpoint](../choosing-graph/SKILL.md#review-checkpoint) before archiving. Reuse a completed wrap-up result. A current-agent task applies that checkpoint here. Record one review disposition for the completed change-set.

After dispatch cleanup, remove a team-mode worktree with plain git. If the primary checkout tracks the merged base, is clean, and is intended for subsequent direct work, fast-forward it using its established tracking configuration. Update an originating tracker ticket once its lifecycle is complete.

**Complete when:** the completion reference and review are recorded, any dispatch is wrapped up, the worktree is removed, and the originating ticket reflects the result.
