---
name: shipping-task
description: Carries one task through a standardized git lifecycle in one of the project's managed apps. Normally invoked by `boss-say` once it has triaged a request down to a single unit of work, or by `troubleshooting-app` once it has scoped a reported failure; also usable directly when the user names it. Not for deciding how work gets dispatched (`boss-say` owns that), scoping/planning the task (your project's task-scoping skill), picking the app (`work-on`, invoked internally here), or many independent tasks at once (`boss-say`'s batch path).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework (including the merge/other-branch-push authorization gate below) this skill operates under — not redefined here.

straw-boss standardizes two lifecycle shapes across every managed app: **team-mode** (worktree → develop → MR → merge → archive) and **solo-mode** (develop directly in the app's primary checkout, commit straight to the base branch). Which one applies is how the user regards this piece of work, so Task 2 asks them — except where the resolved app's `apps.json` entry sets `forbidDirectCommit: true`, in which case only team-mode is offered. Scoping the task happens before this skill. Picking the app happens as this skill's own first step, via `work-on`.

The work itself happens in a session dispatched into the target app (`dispatching-work`), not in this session. An app may already have its own worktree/release tooling — check its `apps.json` entry's `gitWorkflowSkill` field. When it's set, the worker follows it for delivery and this skill only confirms the outcome. Where an app has none, this skill's fallback lifecycle below applies.

**Commit needs no authorization — the agent commits on its own as it goes. Neither does pushing the task's own feature branch** (opening or updating an MR/PR against it) — the branch was already implicitly authorized when the main agent created it; the agent reports with `send-dispatch-message.py --to main --intent inform` and continues, or records progress when no live route exists. **Merge is the mutation the agent cannot self-authorize** — as is any push that lands on another tracked branch: the agent stops and persists `awaiting-authorization` instead.

## Task Initialization

This spans many turns — dispatch now, develop over an unknown number of turns inside the agent, authorize the mutation possibly much later. Track it with TaskCreate, one task per stage, so progress survives context compaction or a session resume. In solo-mode, there's no authorization checkpoint at all — the agent commits straight to the base branch and reports completion directly; don't create a placeholder task for a stop that never happens.

## Task 1: Resolve the app

Invoke the `work-on` skill now if the target app isn't already established in this conversation — do not guess an app here, and do not treat resolution as something that already happened elsewhere. `boss-say` triages scale, not apps; this skill owns making sure resolution actually ran. `work-on` ends at naming the resolved app(s) for implementation work — it does not dispatch itself; that happens in Task 4 below, once this skill has assembled the full instruction.

**Verification:** you can name the app and its directory, sourced from `work-on`.

## Task 2: Ask which mode this work is

Ask the user how they regard this piece of work — solo work they are carrying themselves, or team work that lands through review. Their reading of the work is the whole question. Determine the base/integration branch, and check the resolved app's `apps.json` entry for `forbidDirectCommit` while you're at it (if the field is absent, treat it as `false` — no direct-commit restriction — rather than asking the user to guess).

- **solo-mode**: no worktree, develop directly in the app's primary checkout, commit straight to the base branch — no authorization needed, no MR. Say that much when you offer it, so the user is answering with the consequence in view. `forbidDirectCommit` (below) is the only gate on this path; once a task is offered solo-mode, its commit lands with no further check. The primary checkout is shared and unisolated — unlike a team-mode worktree, nothing keeps a solo-mode task's in-progress changes from colliding with anything else that touches the same checkout. Before dispatching one, check it's clean (`git -C <app_dir> status --porcelain`); a dirty tree almost always means an earlier solo-mode task's change is still mid-work or was abandoned — resolve that first rather than dispatching into contended state. Never have more than one solo-mode task in flight against the same app at once, for the same reason.
- **team-mode**: worktree → develop → MR → merge → archive.

If `forbidDirectCommit` is `true`, say so and only offer team-mode — do not ask the user to pick something the app itself blocks.

**Verification:** the user explicitly picked a mode, or the app forced one and you said so, and you can name the base branch, before assembling the dispatch instruction.

## Task 3: Determine git-lifecycle ownership

**Worktree creation itself is never delegated, regardless of what the app owns.** In team-mode, this skill (via `dispatching-work`) has the main agent create the worktree with plain `git worktree add` (never `herdr worktree create`) before dispatch. See `dispatching-work`'s `references/plan-mechanics.md` "Worktree ownership" section, including its mandatory verify-and-repair and `localFiles` copy steps. The launcher uses the verified worktree as cwd while splitting a worker pane into the coordinator's current tab. In solo-mode there is no worktree.

For everything **after** the worktree exists (or in solo-mode, from the start): check the resolved app's `gitWorkflowSkill` field. This git-lifecycle choice is independent from the target app's own development and SDD route, which runs inside the dispatched session after it enters the app. If `gitWorkflowSkill` is set, the worker runs that skill's remaining steps (commit, and push/MR for the task's own feature branch) to completion on its own, inside the worktree the main agent already created — no authorization needed for any of that — but stops before merge, and before any push that skill's release mechanics might perform against a branch other than the task's own feature branch (a version-bump or release-tag push to a protected/base branch). If it's unset, this skill's own fallback steps apply:

- **team-mode fallback**: develop inside the main-agent-created worktree, committing to the feature branch freely, then push the branch and open an MR/PR on its own. Report the branch + MR/PR reference through the instruction-keyed message script, or `report-progress.py` when no live route exists. Continue; only stop before merge or another-branch push.
- **solo-mode fallback**: develop directly in the primary checkout, then commit straight to the base branch — no authorization needed, no Task 5 stop in solo-mode; report completion once committed.

**Verification:** you can state whether the target app owns its post-worktree git lifecycle or is getting the fallback steps, before Task 4 assembles the instruction; in team-mode, worktree creation itself was never left to the agent's own skill.

## Task 4: Assemble and dispatch

Build an outcome-oriented brief for `dispatching-work`:

- Follow `dispatching-work` Task 3's brief boundary; target-app context discovery
  belongs to the worker.
- Carry forward the **user requirement and requested outcome** and why it matters.
- Add only already-known coordination facts, exact artifact references supplied
  by the workflow, and material task-specific constraints.
- The worker and user choose the **specification, design, implementation, and
  the verification method inside the reality anchor the brief names** in the
  dispatched session.
- Include a constraint only when it is verified, task-specific, and materially changes the acceptable result. Prefer a positive statement with its reason over a preventive list of things not to do.
- Omit **generic lifecycle prose**, reporting commands, provider routing, checkpoint mechanics, tracker policy, and defensive reminders already supplied by the generated contract, this skill, or the target app's own instructions.

The generated contract supplies exact progress, message, checkpoint, and terminal-status mechanics for every provider. Pass the concise task brief, both provider kinds, and the validated main pane/provider-fingerprint pair to `dispatch-task.py write`.

**Verification:** the brief is understandable without the main agent's private
context; every paragraph carries the user requirement, requested outcome,
an already-known coordination fact, or a material task-specific constraint.

## Task 5: Authorize merge, relay push notifications, resume through to completion

Applies to team-mode only — solo-mode's commit needs no authorization and reaches no checkpoint here (Task 2/Task 3).

For an interactive task, authorization happens directly in the dispatched agent's session: point the user to its pane and leave the conversation there. For a headless task, relay the user's answer through its recorded continuation. The main agent never decides for the user.

`awaiting-authorization` remains non-terminal until the user answers. Plan tasks expose it through `watch-plan-status.py`; a standalone task persists the checkpoint to its own `.status.json` sibling and notifies this session from the same call, and the answer arrives as its next status event.

**A feature-branch push notification is not this checkpoint.** The agent pushes its own feature branch and opens or updates an MR/PR on its own — no authorization to obtain and no session to resume. Relay the herdr FYI when it arrives; if no live route exists, read the progress trail. Never convert it into `awaiting-authorization`.

`awaiting-user-input` follows the same direct-user or headless-relay route, but grants no mutation authorization.

`awaiting-main-agent` is reserved for integrated context or a coordinator-owned
action result. Resolve it with `reply-to-worker.py`; a work-content decision
returns to the user in the dispatched agent's session.

If the target app is itself a submodule of a monorepo root and a pointer-bump push at the root is also needed once its commit lands, that's a separate mutation, gated the same way merge is — ask about it separately, don't fold it into the feature-branch push's no-authorization exemption.

**Verification:** every gated mutation has direct user authorization in the interactive task or a faithfully relayed user answer for headless mode; feature-branch pushes remain FYIs.

## Task 6: Confirm and wrap up

Once the agent reports the lifecycle is complete (merged in team-mode,
committed in solo-mode), confirm the merge or commit reference. Then invoke
`dispatching-work`'s wrap-up branch, which closes the worker pane and
instruction and releases any shared-resource lock still held on it; in
team-mode, remove the worktree with plain git. The coordinator's shared tab
remains open.

If the primary checkout tracks the merged base, is clean, and is intended for
subsequent direct work, fast-forward it after removing the team-mode worktree.
Use the app's established remote/tracking configuration. When those conditions
do not hold, report the merged reference and leave checkout synchronization to
the owning workflow.

If the task originated from a tracker ticket, this skill (not the agent) updates it now that the lifecycle is actually complete.

**Verification:** the completion reference is confirmed, not assumed; the dispatch instruction is wrapped up, not left `in-progress`; in team-mode, the worktree is removed by this skill; any originating ticket is updated by this skill, not the agent.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md` — `forbidDirectCommit`/`gitWorkflowSkill` field definitions.
- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/shared-resource-coordination.md` — deterministic port derivation and the cross-main-agent resource lock.
