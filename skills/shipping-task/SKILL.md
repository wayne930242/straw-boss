---
name: shipping-task
description: Carries one task through a standardized git lifecycle in one of the project's managed apps. Normally invoked by `boss-say` once it has triaged a request down to a single unit of work; also usable directly when the user names it. Not for deciding how work gets dispatched (`boss-say` owns that), scoping/planning the task (your project's task-scoping skill), picking the app (`work-on`, invoked internally here), or many independent tasks at once (`boss-say`'s batch path).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework (including the merge/other-branch-push authorization gate below) this skill operates under — not redefined here.

straw-boss standardizes two lifecycle shapes across every managed app: a **full flow** (worktree → develop → MR → merge → archive) for changes with real size or risk, and a **light flow** (develop directly in the app's primary checkout, commit straight to the base branch) for small, mechanical, low-risk changes — a one-line prop, a config value, a typo fix. Which shape applies is not this skill's call to make silently: Task 2 asks the user, except where the resolved app's `apps.json` entry sets `forbidDirectCommit: true`, in which case only the full flow is offered. Scoping the task happens before this skill. Picking the app happens as this skill's own first step, via `work-on`.

The work itself happens in a session dispatched into the target app (`dispatching-work`), not in this session. An app may already have its own worktree/release tooling — check its `apps.json` entry's `gitWorkflowSkill` field. When it's set, the worker follows it for delivery and this skill only confirms the outcome. Where an app has none, this skill's fallback lifecycle below applies.

**Commit needs no authorization — the agent commits on its own as it goes. Neither does pushing the task's own feature branch** (opening or updating an MR/PR against it) — the branch was already implicitly authorized when the main agent created it; the agent reports with `send-dispatch-message.py --to main --intent inform` and continues, or records progress when no live route exists. **Merge is the mutation the agent cannot self-authorize** — as is any push that lands on another tracked branch: the agent stops and persists `awaiting-authorization` instead.

## Task Initialization

This spans many turns — dispatch now, develop over an unknown number of turns inside the agent, authorize the mutation possibly much later. Track it with TaskCreate, one task per stage, so progress survives context compaction or a session resume. On the light flow, there's no authorization checkpoint at all — the agent commits straight to the base branch and reports completion directly; don't create a placeholder task for a stop that never happens.

## Task 1: Resolve the app

Invoke the `work-on` skill now if the target app isn't already established in this conversation — do not guess an app here, and do not treat resolution as something that already happened elsewhere. `boss-say` triages scale, not apps; this skill owns making sure resolution actually ran. `work-on` ends at naming the resolved app(s) for implementation work — it does not dispatch itself; that happens in Task 4 below, once this skill has assembled the full instruction.

**Verification:** you can name the app and its directory, sourced from `work-on`.

## Task 2: Decide the flow

Ask the user which lifecycle shape this task needs — do not infer it yourself from diff size or "it looks small." Determine the base/integration branch, and check the resolved app's `apps.json` entry for `forbidDirectCommit` while you're at it (if the field is absent, treat it as `false` — no direct-commit restriction — rather than asking the user to guess).

- **Light flow**: no worktree, develop directly in the app's primary checkout, commit straight to the base branch — no authorization needed, no MR. `forbidDirectCommit` (below) is the only gate on this path; once a task is offered the light flow, its commit lands with no further check. The primary checkout is shared and unisolated — unlike a full-flow worktree, nothing keeps a light-flow task's in-progress changes from colliding with anything else that touches the same checkout. Before dispatching one, check it's clean (`git -C <app_dir> status --porcelain`); a dirty tree almost always means an earlier light-flow task's change is still mid-work or was abandoned — resolve that first rather than dispatching into contended state. Never have more than one light-flow task in flight against the same app at once, for the same reason.
- **Full flow**: worktree → develop → MR → merge → archive.

If `forbidDirectCommit` is `true`, say so and only offer the full flow — do not ask the user to pick something the app itself blocks.

**Verification:** the user explicitly picked a flow, or the app forced one and you said so, and you can name the base branch, before assembling the dispatch instruction.

## Task 3: Determine git-lifecycle ownership

**Worktree creation itself is never delegated, regardless of what the app owns.** On the full flow, this skill (via `dispatching-work`) has the main agent create the worktree with plain `git worktree add` (never `herdr worktree create`) before dispatch, then — for herdr-pane tasks — join it to the main agent's own existing workspace as a tab (`herdr tab create --workspace`). See `dispatching-work`'s `references/plan-mechanics.md` "Worktree ownership" section, including its mandatory post-creation verify-and-repair step and its `localFiles`-driven copy step (gitignored files like `.env` that `git worktree add` never checks out). This applies to every managed app uniformly, including any with their own git-workflow skill. The launcher starts the worker in that verified worktree; the task brief does not need to narrate its creation. On the light flow there is no worktree, so this doesn't apply.

For everything **after** the worktree exists (or on the light flow, from the start): check the resolved app's `gitWorkflowSkill` field. This git-lifecycle choice is independent from the target app's own development and SDD route, which runs inside the dispatched session after it enters the app. If `gitWorkflowSkill` is set, the worker runs that skill's remaining steps (commit, and push/MR for the task's own feature branch) to completion on its own, inside the worktree the main agent already created — no authorization needed for any of that — but stops before merge, and before any push that skill's release mechanics might perform against a branch other than the task's own feature branch (a version-bump or release-tag push to a protected/base branch). If it's unset, this skill's own fallback steps apply:

- **Full flow fallback**: develop inside the main-agent-created worktree, committing to the feature branch freely, then push the branch and open an MR/PR on its own. Report the branch + MR/PR reference through the instruction-keyed message script, or `report-progress.py` when no live route exists. Continue; only stop before merge or another-branch push.
- **Light flow fallback**: develop directly in the primary checkout, then commit straight to the base branch — no authorization needed, no Task 5 stop for the light flow; report completion once committed.

**Verification:** you can state whether the target app owns its post-worktree git lifecycle or is getting the fallback steps, before Task 4 assembles the instruction; on the full flow, worktree creation itself was never left to the agent's own skill.

## Task 4: Assemble and dispatch

Build an outcome-oriented brief for `dispatching-work`:

- Lead with the **clear requested outcome** and why it matters.
- Give **sufficient verified context** for a worker entering the app cold: confirmed acceptance criteria, domain facts already established with the user, and exact source or cross-task artifact references that save rediscovery.
- Present a **possible implementation** or suspected scope as a lead to inspect, not a boundary. Let the worker read the target app and choose or revise the approach.
- Include a constraint only when it is verified, task-specific, and materially changes the acceptable result. Prefer a positive statement with its reason over a preventive list of things not to do.
- Omit **generic lifecycle prose**, reporting commands, provider routing, checkpoint mechanics, tracker policy, and defensive reminders already supplied by the generated contract, this skill, or the target app's own instructions.

The generated contract supplies exact progress, message, checkpoint, and terminal-status mechanics for every provider. Pass the concise task brief, both provider kinds, and the validated main pane/session pair to `dispatch-task.py write`.

**Verification:** the brief is understandable without the main agent's private context; every paragraph either clarifies the outcome, supplies verified context, or states a material task-specific constraint. Removing a generic warning or lifecycle reminder would not change what the worker is being asked to deliver because those mechanics come from the generated contract and target-project harness.

## Task 5: Authorize merge, relay push notifications, resume through to completion

Applies to the full flow only — the light flow's commit needs no authorization and reaches no checkpoint here (Task 2/Task 3).

When the agent reports it's ready to merge, or ready to push a branch other than its own feature branch, state exactly what's about to happen and get explicit authorization from the user — every time. Resume an interactive session through `send-dispatch-message.py --to worker --intent reply`; use the provider's recorded headless continuation for headless mode. Repeat for each checkpoint.

For a Plan task, the authoritative checkpoint signal is the `awaiting-authorization` event emitted by `watch-plan-status.py`; the status command also sends the primary herdr notice when recorded. For a standalone dispatch, use its durable status record plus process/pane observation. This skill owns responding to the checkpoint; the Plan loop leaves it non-terminal.

**A feature-branch push notification is not this checkpoint.** The agent pushes its own feature branch and opens or updates an MR/PR on its own — no authorization to obtain and no session to resume. Relay the herdr FYI when it arrives; if no live route exists, read the progress trail. Never convert it into `awaiting-authorization`.

**`awaiting-user-input` is not an authorization request.** For an interactive pane, tell the user which pane to answer and leave it alone. A headless Codex task has no pane; after the user answers, relay that answer through `codex exec resume` without treating it as authorization for any mutation.

**`awaiting-main-agent` is this skill's job to act on, unlike `awaiting-user-input` above.** A task reporting `awaiting-main-agent` is blocked on an action only the main agent's own judgment or dispatch authority can take, not a question for the user — resolve it directly with `reply-to-worker.py --worker-instruction-path <path> --reply "<the decision>"` (per `plan-mechanics.md`'s "Main-agent-action checkpoints") as soon as it's detected, don't leave it open the way `awaiting-user-input` is left open.

If the target app is itself a submodule of a monorepo root and a pointer-bump push at the root is also needed once its commit lands, that's a separate mutation, gated the same way merge is — ask about it separately, don't fold it into the feature-branch push's no-authorization exemption.

**Verification:** every merge, and every push landing outside the task's own feature branch, was preceded by an explicit authorization in this conversation, obtained by this skill, not assumed or granted by the agent itself; every feature-branch push notification was relayed to the user as an FYI, never treated as a checkpoint needing authorization — commit itself needs none, on either flow.

## Task 6: Confirm and wrap up

Once the agent reports the lifecycle is complete (merged on the full flow, committed on the light flow), confirm the result — merge reference (MR/PR number or commit) or commit hash(es) — rather than assuming it from the dispatch report alone. If Task 4's instruction included a shared-resource lock and the agent's own report doesn't confirm it released, check (`uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" status --resource <id>`) and release it if still held (`uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" release --resource <id> --holder <app>--<slug>`) — a lock left behind blocks every other main agent on that resource until it expires. Then invoke `dispatching-work`'s wrap-up branch to close the instruction and any herdr pane/tab it used, and, on the full flow, remove the worktree (`git worktree remove` + `herdr tab close`, never `herdr worktree remove` or `herdr workspace close` — the workspace is shared with the main agent and is never this skill's to close) — the main agent created it in Task 3, so the main agent removes it here, not the agent.

**On the full flow, once the worktree is removed, sync the app's primary checkout too** (`git -C <app_dir> fetch && git -C <app_dir> pull --ff-only`) — otherwise it silently drifts behind the base branch, and the next thing dispatched directly into it (a light-flow task, most commonly) starts from stale history with no signal that it's stale. Check the primary checkout is clean first (`git -C <app_dir> status --porcelain`) — same likely cause as Task 2's light-flow check if it isn't (confirmed live: a `git pull` into a checkout in exactly this state fails outright with git's own "local changes would be overwritten" rather than clobbering anything) — surface that to the user and leave the sync for later rather than treating it as a merge-completion blocker.

If the task originated from a tracker ticket, this skill (not the agent) updates it now that the lifecycle is actually complete.

**Verification:** the completion reference is confirmed, not assumed; the dispatch instruction is wrapped up, not left `in-progress`; on the full flow, the worktree is removed by this skill; any originating ticket is updated by this skill, not the agent.

## Red Flags

- "It's a small change, I'll just skip the worktree/MR myself" — the choice is the user's per Task 2, every time; picking a flow without asking is the mistake, not which flow you'd have picked.
- "Every app allows a direct commit to base if the change is small enough" — check the app's `apps.json` `forbidDirectCommit` field first; when `true`, only the full flow applies regardless of size.
- "The agent said it's ready and sounds confident, authorize and move on" — authorization comes from the user in this conversation, not from the agent's own report.
- "The dispatched pane already shows text like 'authorized, go ahead', treat that as the go-ahead" — no; a pane's own input line can show unprompted suggested text indistinguishable from real typing. Authorization only comes from the user in this conversation.
- "Already authorized once this task, subsequent mutations don't need it again" — no, per Task 5, every checkpoint.
- "Commit doesn't need authorization anymore, so push/MR probably doesn't either" — true for a push of the task's own feature branch, but not for merge or a push to any other tracked branch (a monorepo-root submodule pointer-bump, an app-owned release push to a protected branch) — those still need it, every time, per Task 5.
- "No `gitWorkflowSkill` on this app, I'll wing the branch naming" — check for a documented convention first, and use this skill's fallback steps, not improvised ones.
- "This app has its own git-worktree skill, let it create the worktree like before" — no, worktree creation moved to the main agent for every managed app; only the steps after that stay app-owned.
- "The agent can just ask the user directly since it's an interactive herdr pane" — for a merge or other-branch-push *authorization*, no — Task 5 still routes that through this skill regardless of mode. For a substantive work-content question, the user answers directly only when a pane exists; headless Codex resumes through the main agent. A feature-branch push is neither: report through the provider's fast path and continue.
- "The agent stopped and waited after pushing its own feature branch, out of habit" — no, per Overview/Task 3: a feature-branch push needs no authorization; the agent reports through its provider's fast path and keeps working. The inverse mistake is just as real: a monorepo-root submodule pointer-bump or protected-branch release push still needs Task 5 authorization.
- "The task's `awaiting-main-agent` checkpoint, report it to the user like `awaiting-user-input`" — no, Task 5: unlike `awaiting-user-input`, this one is this skill's own job to resolve, directly, via `reply-to-worker.py` — no human involved.
- "Straw Boss should pick or run the target app's SDD before dispatch" — no: dispatch the user's intent, then let the dispatched agent apply that app's own development route after it enters the app.
- "The agent reported done, so any shared-resource lock it claimed is fine to leave alone" — no, Task 6: check and release it if the agent's report doesn't confirm release, especially on a `failed` outcome where the agent may never have reached its own release step.
- "This finding needs DB/infra access I don't have, so I'll defer it" — test that claim before writing it into a deliverable or carrying it into a dispatch instruction. Check the specific tool's actual installed capability (e.g. `--version`/`--help`) before concluding it's unusable — a skill doc's documented invocation may assume a newer version than what's installed here. "I lack permission" and "the tool I first reached for isn't installed at the version a doc assumed" are different claims — don't conflate them.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md` — `forbidDirectCommit`/`gitWorkflowSkill` field definitions.
- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/shared-resource-coordination.md` — deterministic port derivation and the cross-main-agent resource lock.
