---
name: shipping-task
description: Carries one task through a standardized git lifecycle in one of the project's managed apps. Normally invoked by `boss-say` once it has triaged a request down to a single unit of work, or by `troubleshooting-app` once it has scoped a reported failure; also usable directly when the user names it. Not for deciding how work gets dispatched (`boss-say` owns that), scoping/planning the task (your project's task-scoping skill), picking the app (`work-on`, invoked internally here), or many independent tasks at once (`boss-say`'s batch path).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework (including the merge/other-branch-push authorization gate below) this skill operates under — not redefined here.

straw-boss standardizes two lifecycle shapes across every managed app: **team-mode** (worktree → develop → MR → merge → archive) and **solo-mode** (develop directly in the app's primary checkout, commit straight to the base branch). Which one applies is how the user regards this piece of work, so Task 2 asks them — except where the resolved app's `apps.json` entry sets `forbidDirectCommit: true`, in which case only team-mode is offered. Scoping the task happens before this skill. Picking the app happens as this skill's own first step, via `work-on`.

The execution tier comes from `boss-say`: a bounded single-loop stays with the current agent; work needing a separate durable workroom uses `dispatching-work`. An app may already own its git lifecycle through `apps.json.gitWorkflowSkill`; otherwise the fallback below applies.

**Commit needs no authorization — the agent commits on its own as it goes. Neither does pushing the task's own feature branch** (opening or updating an MR/PR against it) — the branch was already implicitly authorized when the main agent created it; the agent reports with `send-dispatch-message.py --to main --intent inform` and continues, or records progress when no live route exists. **Merge is the mutation the agent cannot self-authorize** — as is any push that lands on another tracked branch: the agent stops and persists `awaiting-authorization` instead.

## Task Initialization

Create durable task tracking when the selected execution tier spans turns or checkpoints. A bounded single-loop needs no extra lifecycle bookkeeping.

## Task 1: Resolve the app

Invoke `work-on` when the target app is not established. It returns the app and directory; the execution tier remains the one selected by `boss-say`.

**Verification:** you can name the app and its directory, sourced from `work-on`.

## Task 2: Ask which mode this work is

Ask the user how they regard this piece of work — solo work they are carrying themselves, or team work that lands through review. Their reading of the work is the whole question. Determine the base/integration branch, and check the resolved app's `apps.json` entry for `forbidDirectCommit` while you're at it (if the field is absent, treat it as `false` — no direct-commit restriction — rather than asking the user to guess).

- **solo-mode**: no worktree, develop directly in the app's primary checkout, commit straight to the base branch — no authorization needed, no MR. Say that much when you offer it, so the user is answering with the consequence in view. `forbidDirectCommit` (below) is the only gate on this path; once a task is offered solo-mode, its commit lands with no further check. The primary checkout is shared and unisolated — unlike a team-mode worktree, nothing keeps a solo-mode task's in-progress changes from colliding with anything else that touches the same checkout. Before dispatching one, check it's clean (`git -C <app_dir> status --porcelain`); a dirty tree almost always means an earlier solo-mode task's change is still mid-work or was abandoned — resolve that first rather than dispatching into contended state. Never have more than one solo-mode task in flight against the same app at once, for the same reason.
- **team-mode**: worktree → develop → MR → merge → archive.

If `forbidDirectCommit` is `true`, say so and only offer team-mode — do not ask the user to pick something the app itself blocks.

**Verification:** the user explicitly picked a mode, or the app forced one and you said so, and you can name the base branch before work starts.

## Task 3: Determine git-lifecycle ownership

**Worktree creation itself is never delegated, regardless of what the app owns.** In team-mode, the current agent creates and verifies the worktree with plain `git worktree add` (never `herdr worktree create`). See `dispatching-work`'s `references/plan-mechanics.md` "Worktree ownership" section for the verify-and-repair and `localFiles` copy steps. If a separate workroom was selected, its launcher uses that verified worktree as cwd. In solo-mode there is no worktree.

For everything **after** the worktree exists (or in solo-mode, from the start), check the resolved app's `gitWorkflowSkill` field. This git-lifecycle choice is independent from the target app's development and SDD route. If `gitWorkflowSkill` is set, the execution owner runs that skill's remaining steps (commit, and push/MR for the task's own feature branch) to completion — no authorization is needed for those steps — but stops before merge or any push to another tracked branch. If it is unset, this skill's fallback steps apply:

- **team-mode fallback**: develop inside the current-agent-created worktree, commit to the feature branch, then push the branch and open an MR/PR. The current agent reports directly; a separate workroom uses its instruction-keyed message or progress route. Continue until merge or another-branch push needs authorization.
- **solo-mode fallback**: develop directly in the primary checkout, then commit straight to the base branch — no authorization needed, no Task 5 stop in solo-mode; report completion once committed.

**Verification:** you can state whether the target app owns its post-worktree git lifecycle or is getting the fallback steps, before Task 4 assembles the instruction; in team-mode, worktree creation itself was never left to the agent's own skill.

## Task 4: Execute in the selected tier

For a current-agent single-loop, load the target checkout's instructions and carry the task through implementation, its reality anchor, and the selected git lifecycle here.

For a separate workroom, build an outcome-oriented brief for `dispatching-work`:

- Follow `dispatching-work` Task 3's brief boundary; target-app context discovery belongs to the worker.
- Carry forward the **user requirement and requested outcome** and why it matters.
- Add only already-known coordination facts, exact artifact references supplied
  by the workflow, and material task-specific constraints.
- The worker and user choose the **specification, design, implementation, and the verification method inside the reality anchor the brief names** in the dispatched session.
- Carry the review checkpoint selected by `choosing-graph`; the completed change-set is reviewed once by its lifecycle owner.
- Include a constraint only when it is verified, task-specific, and materially changes the acceptable result. Prefer a positive statement with its reason over a preventive list of things not to do.
- Omit **generic lifecycle prose**, reporting commands, provider routing, checkpoint mechanics, tracker policy, and defensive reminders already supplied by the generated contract, this skill, or the target app's own instructions.

The generated contract supplies exact progress, message, checkpoint, and terminal-status mechanics for every provider. Pass the concise task brief, both provider kinds, and the validated main pane/provider-fingerprint pair to `dispatch-task.py write`.

**Verification:** the current agent is working from the resolved checkout with its instructions loaded, or the dispatched brief is understandable without private context and contains only the requirement, outcome, known coordination facts, and material constraints.

## Task 5: Authorize merge, relay push notifications, resume through to completion

Applies to team-mode only — solo-mode's commit needs no authorization and reaches no checkpoint here (Task 2/Task 3).

For a current-agent single-loop, ask the user here. For an interactive task, authorization happens directly in the dispatched agent's session. Headless Codex resumes its recorded thread with the answer. Headless Claude reports terminal `failed`; after the answer, wrap that attempt and start a fresh-slug dispatch carrying the answer, using `--retry-failed-plan-task` for a plan task.

For an interactive or headless Codex task, `awaiting-authorization` remains non-terminal until the user answers. Plan tasks expose it through `watch-plan-status.py`; a standalone task persists the checkpoint to its own `.status.json` sibling and notifies this session from the same call, and the answer arrives as its next status event.

**A feature-branch push notification is not this checkpoint.** The agent pushes its own feature branch and opens or updates an MR/PR on its own — no authorization to obtain and no session to resume. Relay the herdr FYI when it arrives; if no live route exists, read the progress trail. Never convert it into `awaiting-authorization`.

`awaiting-user-input` follows the same interactive or headless Codex route, but grants no mutation authorization. A headless Claude user decision uses its terminal failed-and-retry route.

`awaiting-main-agent` is reserved for integrated context or a coordinator-owned action result. Interactive tasks resolve it with `reply-to-worker.py`; headless Codex resumes its thread with the result, while headless Claude uses its terminal failed-and-retry route. A work-content decision returns to the user.

If the target app is itself a submodule of a monorepo root and a pointer-bump push at the root is also needed once its commit lands, that's a separate mutation, gated the same way merge is — ask about it separately, don't fold it into the feature-branch push's no-authorization exemption.

**Verification:** every gated mutation has direct user authorization in the interactive task or a faithfully relayed user answer for headless mode; feature-branch pushes remain FYIs.

## Task 6: Confirm and wrap up

For a `work-on`-produced plan (Task 1), this task runs once per plan task, as each one's own lifecycle completes — not once for the whole plan.

Confirm the merge or commit reference, then record the single review disposition required by `choosing-graph` against that reference. For a dispatched task, invoke `dispatching-work`'s wrap-up branch to close its pane, instruction, and shared-resource locks. In team-mode, remove the worktree with plain git.

If the primary checkout tracks the merged base, is clean, and is intended for subsequent direct work, fast-forward it after removing the team-mode worktree. Use the app's established remote/tracking configuration. When those conditions do not hold, report the merged reference and leave checkout synchronization to the owning workflow.

If the task originated from a tracker ticket, this skill (not the agent) updates it now that the lifecycle is actually complete.

**Verification:** the completion reference and one review disposition are confirmed; each plan task closes once; any dispatch is wrapped up; a team-mode worktree is removed; any originating ticket is updated.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md` — `forbidDirectCommit`/`gitWorkflowSkill` field definitions.
- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/shared-resource-coordination.md` — deterministic port derivation and the cross-main-agent resource lock.
