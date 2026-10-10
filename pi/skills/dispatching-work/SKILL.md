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

Apply the role and thinking rules in the user instructions, then the work route in the root `AGENTS.md` of the repository holding the apps configuration, which may map a kind of task to a role.
Leave `model` unset unless the user chose one explicitly.
State the selected role, thinking level, and reason.

### Prepare the checkout

Solo-mode work and read-only work launch with the app directory as `cwd`.

Team-mode work runs in a worktree this session owns:

1. Create and verify it with plain git from the app directory resolved by [resolving-app](../resolving-app/SKILL.md):

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

- **The work** — the user requirement and requested outcome, stated per item as the current symptom and the required behavior, plus any input or artifact path the worker cannot reach from its own checkout. What this session already found travels as evidence references, such as a reproduction, report, or session file, for the worker to weigh.
- **The anchor and who exercises it** — this task's anchor and the behavior it observes, and whether the worker runs its own checkpoint or hands its completion reference and evidence to the group's shared one. The worker and user choose the verification method inside that anchor.
- **Its place and motive** — where this task sits in the coordination and the user's original reason for it.
- **Authorizations** — every authorization and exclusion the user stated for this work, quoted.

Target-app context discovery and work decisions stay with the worker: the cause, where to change the code, the app's conventions, and its verification commands stay out, because a prescribed cause or location binds the worker to an unverified guess.
Process rules reach the worker through its role definition and the user instructions every Pi session loads.
Keep the brief before the worker contract near 300 words, quoted user text aside; 101 sampled briefs with a 598-word median there were mostly this excluded material.
Name a method skill only when the user explicitly requested it.

The brief ends with this worker contract:

> Work in this checkout and follow its own instructions. When you need a decision that the authorizations above do not cover, call `caller_ping`, then stop; the answer arrives when this session resumes. Give the review disposition in your final message when this brief assigns the review checkpoint to you. For an investigation or audit, give evidence references.

### Launch

Call `subagent` with `name` (`<task>-<role>[-n]`), `agent` (the role), `thinking`, `cwd`, and `task`.
Track the dispatch as an in-progress todo item and report its name, role, and `cwd`.
Read its pane with `herdr pane read <pane_id> --lines 15` once Pi has started; a worker held at a trust prompt gets the trust-parent-folder choice through `herdr pane send-keys`, because an unanswered prompt has left a worker idle for hours.

## Handle events

Each delivered event starts one [scheduling round](../boss-say/SKILL.md#plan-and-schedule).

| Event | Action |
|---|---|
| `subagent_result` or `recovered_dispatch_result` | Check it against the brief, wrap up below, and update the dispatch's todo item before the round schedules anything else. |
| `caller_ping` | Gather every pending decision from all workers, ask them together through `ask_user` with each one's context, options, and recommendation, then continue each worker with `subagent_resume` carrying its answer. The worker keeps its slot meanwhile. |
| Stall notice | Interrupt the worker once with `subagent_interrupt`, which keeps it open, and ask for its result with `herdr pane send-text <pane_id> "<request>"` followed by `herdr pane send-keys <pane_id> enter`. If it stays idle, end it with `subagent_cancel`, report it, and respawn only the work still missing. `subagent_cancel` delivers one cancelled result and launches no fallback model. On macOS a worktree worker's cancel reports `unconfirmed`; close its pane with `herdr pane close <pane_id>` and call `subagent_cancel` again. Closing a live worker's pane before the cancel is recorded counts as a failure and relaunches it on the next fallback model. |

## Wrap up

A dispatch is `done` only when every item below holds:

1. The result carries what the brief asked for: a completion reference for a source change, or an explanatory result with evidence references for an investigation or audit.
2. The task's checkpoint has run. A source change resolves the [review checkpoint](../choosing-graph/SKILL.md#review-checkpoint) and records a disposition against the completion reference; a task under a shared checkpoint takes its disposition from that checkpoint task. An adversarial-review anchor launches one fresh-context `subagent` in an ordinary pane, named `<task>-review`, with the `reviewer` role; its brief carries the requirement, the result, and its evidence references, and asks for a verdict of pass, pass with nits, or fail with each finding's evidence. Nits on a read-only result are corrected in the report to the user.
3. Open review findings are resolved or returned as fix tasks.

A task under a shared checkpoint that meets item 1 is `delivered`, as [boss-say](../boss-say/SKILL.md#plan-and-schedule) defines; keep its worktree until the checkpoint task returns.

Then update the originating ticket as [shipping-task](../shipping-task/SKILL.md#complete-the-lifecycle) directs, while the worktree still exists for a tracker that reads its commit there; remove a worktree this session created with `git -C "<app_dir>" worktree remove "<absolute-worktree-path>"`.

Every result settles its todo item:

- `done`: mark the item `completed`, which unblocks its dependents.
- `delivered`: keep it `in_progress`, noted, until the checkpoint task returns.
- A result missing item 1, or a failed checkpoint: set the item back to `pending` with the failure in its description and add a fix task it depends on; its dependents stay blocked.
`pi-herdr-agents` closes an ordinary worker pane after delivery.

## Recover and hand off

Use the `dispatch_control` tool:

- `roll-call` lists this session's dispatches, one per line as `id | status | name | last pane | session file`.
- `reattach` with a dispatch `id` resumes a stopped worker in its pane; a pane still running a foreground process keeps it.
- `handoff` with a `summary` transfers this scope to a new Herdr tab after the user approves the transfer. The summary carries the scope, confirmed decisions, anchors, pending user decisions, and every undispatched task with its dependencies.

Results arrive once while the owning Pi process runs, and at least once across a crash.

**Complete when:** each dispatch is launched and tracked, or its result, checkpoint, review disposition, ticket update, worktree removal, and todo item status are confirmed.
