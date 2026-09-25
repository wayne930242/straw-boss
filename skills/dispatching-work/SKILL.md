---
name: dispatching-work
description: Use to launch, track, list, or wrap up a resolved app-rooted dispatch.
---

## Prepare the dispatch

The caller resolves the app and execution tier.
This skill owns instruction creation, launch, checkpoint handling, and cleanup.
[boss-say](../boss-say/SKILL.md#plan-and-schedule) owns plan scheduling; a `batch` label only groups dispatches.

Before writing an instruction, confirm `herdr status` and the current `$HERDR_PANE_ID` live record.
Report an unavailable dependency and continue dispatch only from a reachable Herdr session.
Resolve the worker's provider/profile/model/effort through [work-route resolution](references/dispatch-mechanics.md#resolve-mode-and-work-route), map the main agent's restriction tier through [permission mapping](references/dispatch-mechanics.md#permission-mapping), and state the selected setup and reason.

Register through [contacting-orchestrators](../contacting-orchestrators/SKILL.md), then record this session's pane and provider fingerprint using [Record the main agent before launch](references/cross-session-coordination.md#record-the-main-agent-before-launch).
Team-mode cwd preparation belongs to [shipping-task](../shipping-task/SKILL.md#prepare-and-execute).

## Write the brief

A brief carries three things:

- **The work** -- the user requirement and requested outcome, plus any input, artifact path, or assigned port the worker cannot reach from its own harness.
- **The anchor and who exercises it** -- this task's anchor, and whether the worker runs its own checkpoint or hands its completion reference and evidence to the group's shared one. The worker and user choose the verification method inside that anchor.
- **Its place and motive** -- where this task sits in the coordination and the user's original reason for it.

Target-app context discovery and work decisions stay with the worker in its own harness, so repo conventions, implementation direction, and anything else readable from that checkout stay out.
Name a method skill only when the user explicitly requested it; the app chooses its own methods otherwise.
Investigation and audit briefs request an explanatory result with evidence references.

Apply [choosing-graph](../choosing-graph/SKILL.md) if the graph and anchor are unset.
A task whose checkpoint is shared passes `--shared-checkpoint` to the write command below, so its brief and contract ask for implementation, its own working verification, and the reference and evidence that checkpoint reads.
A [checkpoint task](../choosing-graph/SKILL.md#review-checkpoint) gets a review-only brief whose work is every covered task's requirement, completion reference, and evidence references.

The generated contract supplies lifecycle, progress, message, checkpoint, and review-disposition mechanics.

Call [dispatch-task.py write](references/dispatch-mechanics.md#write-the-instruction-and-contract) with the resolved setup and main-agent identity.
A plan task also supplies `plan_id`/`task_id`; the command marks the planned task dispatched.
The generated instruction and hashed contract must exist with `pending` status before launch.

## Launch

Run [launch-dispatched-agent.py](references/dispatch-mechanics.md#interactive-herdr-launch) in the foreground and resume the same tool call until it exits.
The launcher owns the same-tab pane split, contract injection, bounded retries, delivery verification, receipt, and confirmation.

Read the result before reporting success.
Require `confirmed: true` and instruction status `in-progress`; if confirmation failed, follow the returned repair command.
A launch failure follows [When a launch fails](references/dispatch-mechanics.md#when-a-launch-fails), preserving any reachable pane the launcher retained.

Report the task, instruction path, and worker pane/tab.

## Handle events

Persisted status drives the lifecycle.
A plan uses the [status watcher](references/plan-mechanics.md#monitor-plan-status); standalone status is the instruction's `.status.json` sibling.
Between events, continue other coordination or the user's conversation.

| Event | Main-agent action |
|---|---|
| `awaiting-main-agent` | Supply verified cross-task context or a coordinator-owned action result through `reply-to-worker.py --worker-instruction-path <path> --reply <answer>`. Route a work decision to the user. |
| `awaiting-user-input` / `awaiting-authorization` | Point the user to the worker pane; present useful coordination facts and references directly to the user in your own conversation. `control` and `redirect` are deliberately refused in these states, because they direct the worker while the user owns the decision; `--intent inform` stays open for verified findings the worker will need. The user acts in the worker's pane, or the coordinator ends the task with `close-worker-pane.py`; retain the task and its slot until its next status event. |
| `done` / `failed` / `cancelled` | Check [same-task continuation](references/plan-mechanics.md#same-task-continuation), then wrap up when the logical task has ended. Return the result to the scheduler. |
| Feature-branch push FYI | Relay the update; slot accounting and task status stay as recorded. |

Read live progress through [peeking-work](../peeking-work/SKILL.md) when the user asks or evidence contradicts recorded state.
[Cross-session coordination](references/cross-session-coordination.md) owns redirect, cancellation, identity-rebind, and user-requested takeover mechanics.

## List outstanding dispatches

Run [roll-call.py](references/dispatch-mechanics.md#roll-call).
It reconciles instructions, receipts, launch failures, and live provider identity.
Use `--mine` for this session's dispatch list.
An `unattributed` pane has unknown ownership; resolve that ownership before taking action on it.
A pane listed under wrapped-up dispatches is the opposite case: its archived instruction still names it, so close it with the listed command.

## Wrap up

1. Resolve the canonical instruction and any confirmed same-task continuation. A continuation retains its instruction and pane until that logical task finishes.
2. Require terminal status (`done`, `failed`, or `cancelled`). For a reachable worker at a checkpoint, use the event route above. If its pane is confirmed closed, or its live worker's own report is refused, and status is missing or non-terminal, use [recover-task-status.py](references/dispatch-mechanics.md#recover-a-closed-worker) with evidence supporting `done` or `failed`. A pending instruction that never launched can be archived without a status record.
3. For a landed programming change, resolve [choosing-graph's review checkpoint](../choosing-graph/SKILL.md#review-checkpoint): confirm the completion reference and existing review disposition, or complete the missing review before cleanup. A task with a shared checkpoint records its completion reference here and takes its disposition from that checkpoint task, so it wraps up on its own terminal status.
4. Close only the terminal worker's pane, through [close-worker-pane.py](references/dispatch-mechanics.md#close-a-worker-pane), which rebalances the columns it leaves behind. Release every remaining lock through [Releasing every lock on a wrapped-up instruction](references/shared-resource-coordination.md#releasing-every-lock-on-a-wrapped-up-instruction).
5. Run the archive command below. For a plan task, supply its plan and task id. If the instruction owns its worktree (`worktree_owned: true`), remove it with `git worktree remove <worktree_path>` and return the branch to whatever owns it; a `worktree_path` without that claim is where the dispatch ran, and it stays. Otherwise return to the lifecycle owner for ticket cleanup.

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/wrap-up-task.py" \
  --app <app> --slug <slug> [--plan <plan-slug> --task-id <task-id>]
```

The command archives lifecycle artifacts and synchronizes the plan task's terminal status.
The coordinator pane and shared tab remain open.
Its result's `remaining_steps` names any pane-close and `git worktree remove` command step 4 or this step did not already run -- a safety net for a skipped step, not a substitute for running them here.

**Complete when:** a dispatch is launched and covered by its next status event, or its terminal status, review, pane closure, lock release, and archive are confirmed.
