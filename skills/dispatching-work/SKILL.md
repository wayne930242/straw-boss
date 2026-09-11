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

Carry the user requirement, requested outcome, dependencies, and verified coordination facts already available.
Target-app context discovery and work decisions stay with the worker in its own harness, so the brief carries only what the worker cannot reach from there.
Investigation and audit briefs request an explanatory result with evidence references.

Apply [choosing-graph](../choosing-graph/SKILL.md) if the graph and anchor are unset.
Add the chosen anchor, checkpoint, and any assigned frontend port.
The worker and user choose the verification method inside that anchor.
Name a method skill only when the user explicitly requested it; the app chooses its own methods otherwise.

The generated contract supplies lifecycle, progress, message, and checkpoint mechanics.

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
| `awaiting-user-input` / `awaiting-authorization` | Point the user to the worker pane; retain the task and its slot until its next status event. |
| `done` / `failed` / `cancelled` | Check [same-task continuation](references/plan-mechanics.md#same-task-continuation), then wrap up when the logical task has ended. Return the result to the scheduler. |
| Feature-branch push FYI | Relay the update; slot accounting and task status stay as recorded. |

Read live progress through [peeking-work](../peeking-work/SKILL.md) when the user asks or evidence contradicts recorded state.
[Cross-session coordination](references/cross-session-coordination.md) owns redirect, cancellation, and identity-rebind mechanics.

## List outstanding dispatches

Run [roll-call.py](references/dispatch-mechanics.md#roll-call).
It reconciles instructions, receipts, launch failures, and live provider identity.
Use `--mine` for this session's dispatch list.
An `unattributed` pane has unknown ownership; resolve that ownership before taking action on it.

## Wrap up

1. Resolve the canonical instruction and any confirmed same-task continuation. A continuation retains its instruction and pane until that logical task finishes.
2. Require terminal status (`done`, `failed`, or `cancelled`). For a reachable worker at a checkpoint, use the event route above. If its pane is confirmed closed and status is missing or non-terminal, use [recover-task-status.py](references/dispatch-mechanics.md#recover-a-closed-worker) with evidence supporting `done` or `failed`. A pending instruction that never launched can be archived without a status record.
3. For a landed programming change, resolve [choosing-graph's review checkpoint](../choosing-graph/SKILL.md#review-checkpoint): confirm the completion reference and existing review disposition, or complete the missing review before cleanup.
4. Close only the terminal worker's pane. Release every remaining lock through [Releasing every lock on a wrapped-up instruction](references/shared-resource-coordination.md#releasing-every-lock-on-a-wrapped-up-instruction).
5. Run the archive command below. For a plan task, supply its plan and task id. Return to the lifecycle owner for git worktree and ticket cleanup.

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/wrap-up-task.py" \
  --app <app> --slug <slug> [--plan <plan-slug> --task-id <task-id>]
```

The command archives lifecycle artifacts and synchronizes the plan task's terminal status.
The coordinator pane and shared tab remain open.

**Complete when:** a dispatch is launched and covered by its next status event, or its terminal status, review, pane closure, lock release, and archive are confirmed.
