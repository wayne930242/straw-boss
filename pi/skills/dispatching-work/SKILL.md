---
name: dispatching-work
description: Use to launch, track, recover, or wrap up a resolved app-rooted Pi dispatch.
---

## Launch a dispatch

The caller resolves the app, graph, anchor, and lifecycle mode.
This skill owns worker setup, checkout preparation, the brief, launch, events, recovery, and wrap-up.
[boss-say](../boss-say/SKILL.md#plan-and-schedule) owns scheduling.
Workers are Pi sessions launched by `subagent` from `pi-herdr-agents`; it checks Herdr, opens the pane, and delivers each result back to this session.

### Resolve the worker setup

Pick a tier from the user's active Pi model strategy.
A work route in the root `AGENTS.md` of the repository holding the apps configuration may map a kind of task to a tier; otherwise pick the tier whose purpose matches the task: `recon` for read-only investigation, `review` for a checkpoint review, `coding` for other source changes.
Pass that tier's full model list as `model` and its thinking level as `thinking`, and state the selected tier and reason.
Leave `agent` unset: a bare spawn runs autonomously with the full tool set, including `caller_ping`.

### Prepare the checkout

Solo-mode work and read-only work launch with the app directory as `cwd`.

Team-mode work runs in a worktree this session owns:

1. Create and verify it with plain git from the app directory resolved by [work-on](../work-on/SKILL.md):

   ```bash
   git -C "<app_dir>" worktree add --no-track "<app_dir>-<slug>" -b "<branch>" "<base_branch>"
   git -C "<app_dir>-<slug>" rev-parse --show-toplevel
   ```

   The returned top-level path must be the new worktree; a mismatch blocks this launch.
2. Copy each declared `localFiles` entry from `<app_dir>/<path>` to the same path in the worktree with `cp -R`, keeping any destination that already exists. A missing entry stops this launch with its path and note unless that exact entry has `optional: true`. A `sensitive: true` entry is copied only under user authorization covering it. Report copied and skipped paths; file contents stay unread.
3. Launch with the verified worktree as `cwd`, leaving `subagent`'s own `worktree` option unset.

When parallel tasks target the same moving base, the worker refreshes through the app's merge or rebase workflow before pushing.

### Write the brief

The `task` is written in English and carries:

- **The work** — the user requirement and requested outcome, plus any input or artifact path the worker cannot reach from its own checkout.
- **The anchor and who exercises it** — this task's anchor, and whether the worker runs its own checkpoint or hands its completion reference and evidence to the group's shared one. The worker and user choose the verification method inside that anchor.
- **Its place and motive** — where this task sits in the coordination and the user's original reason for it.
- **Authorizations** — every authorization the user granted for this work, quoted.

Target-app context and work decisions stay with the worker, so repository conventions and implementation direction stay out.
Name a method skill only when the user explicitly requested it.

The brief ends with this worker contract:

> Work in this checkout and follow its own instructions. When you need a decision that the authorizations above do not cover, call `caller_ping` with the question, the options, and your recommendation, then stop; the answer arrives when this session resumes. Finish with one final message. For a source change, give the completion reference (commit, MR/PR, or merge), the evidence references for the anchor's checkpoint, any push of your own feature branch, and the review disposition. For an investigation or audit, give the explanatory result with its evidence references. On failure, give the failure and its evidence.

### Launch

Call `subagent` with `name` (`<task>-<role>[-n]`), `cwd`, `model`, `thinking`, and `task`.
Track the dispatch as an in-progress todo item and report its name, tier, and `cwd`.
`pi-herdr-agents` places the pane in the Herdr workspace that owns the checkout, or in this session's workspace when none does.

## Handle events

Each delivered event starts one [scheduling round](../boss-say/SKILL.md#plan-and-schedule).

| Event | Action |
|---|---|
| `subagent_result` or `recovered_dispatch_result` | Check it against the brief, then wrap up below. |
| `caller_ping` | Gather every pending decision from all workers, ask them together through `ask_user` with each one's context, options, and recommendation, then continue each worker with `subagent_resume` carrying its answer. The worker keeps its slot meanwhile. |
| Stall notice | Report the worker's name and pane to the user. |

## Wrap up

A dispatch is `done` only when every item below holds:

1. The result carries what the brief asked for: a completion reference for a source change, or an explanatory result with evidence references for an investigation or audit.
2. The task's checkpoint has run. A source change resolves the [review checkpoint](../choosing-graph/SKILL.md#review-checkpoint) and records a disposition against the completion reference; a task under a shared checkpoint takes its disposition from that checkpoint task. An adversarial-review anchor launches one fresh-context `subagent` in an ordinary pane, named `<task>-review`, with the review tier; its brief carries the requirement, the result, and its evidence references, and asks for a verdict of pass, pass with nits, or fail with each finding's evidence. Nits on a read-only result are corrected in the report to the user.
3. Open review findings are resolved or returned as fix tasks.

A task under a shared checkpoint that meets item 1 is `delivered`: note it on its todo item and keep its worktree until the checkpoint task returns; that result then settles items 2 and 3 for every covered task.

Then update the originating ticket as [shipping-task](../shipping-task/SKILL.md#complete-the-lifecycle) directs, while the worktree still exists for a tracker that reads its commit there; remove a worktree this session created with `git -C "<app_dir>" worktree remove "<absolute-worktree-path>"`; and check off the todo item.
A result missing item 1, or a checkpoint that fails, marks the task failed or reopens it with a fix task; its dependents stay blocked.
`pi-herdr-agents` closes an ordinary worker pane after delivery.

## Recover and hand off

Use the `dispatch_control` tool:

- `roll-call` lists this session's dispatches, one per line as `id | status | name | last pane | session file`.
- `reattach` with a dispatch `id` resumes a stopped worker in its pane; a pane still running a foreground process keeps it.
- `handoff` with a `summary` transfers this scope to a new Herdr tab after the user approves the transfer. The summary carries the scope, confirmed decisions, anchors, pending user decisions, and every undispatched task with its dependencies.

Results arrive once while the owning Pi process runs, and at least once across a crash.

**Complete when:** each dispatch is launched and tracked, or its result, checkpoint, review disposition, ticket update, and worktree removal are confirmed.
