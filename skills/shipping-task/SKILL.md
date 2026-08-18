---
name: shipping-task
description: Carries one task through a standardized git lifecycle in one of the project's managed apps. Normally invoked by `boss-say` once it has triaged a request down to a single unit of work; also usable directly when the user names it. Not for deciding how work gets dispatched (`boss-say` owns that), scoping/planning the task (your project's task-scoping skill), picking the app (`work-on`, invoked internally here), or many independent tasks at once (`boss-say`'s batch path).
---

## Overview

straw-boss standardizes two lifecycle shapes across every managed app: a **full flow** (worktree → develop → MR → merge → archive) for changes with real size or risk, and a **light flow** (develop directly in the app's primary checkout, commit straight to the base branch) for small, mechanical, low-risk changes — a one-line prop, a config value, a typo fix. Which shape applies is not this skill's call to make silently: Task 2 asks the user, except where the resolved app's `apps.json` entry sets `forbidDirectCommit: true`, in which case only the full flow is offered. Scoping the task happens before this skill. Picking the app happens as this skill's own first step, via `work-on`.

The work itself happens in a session dispatched into the target app (`dispatching-work`), not in this session. An app may already have its own worktree/release tooling — check its `apps.json` entry's `gitWorkflowSkill` field. When it's set, the dispatch instruction tells the agent to run that skill to completion, and this skill only confirms the outcome. Where an app has none, this skill's own fallback steps below travel in the dispatch instruction instead.

**Commit/push/merge are external mutations, and the agent cannot self-authorize them** — every dispatch instruction this skill assembles explicitly tells the agent to stop and report back once it's ready to commit/push/merge, not execute it. This skill (interactive with the actual user) obtains authorization and resumes the agent to proceed. This holds for both dispatch modes and regardless of which app owns its own git-workflow skill.

## Task Initialization

This spans many turns — dispatch now, develop over an unknown number of turns inside the agent, authorize the mutation possibly much later. Track it with TaskCreate, one task per stage, so progress survives context compaction or a session resume. On the light flow, most stages collapse to a single commit checkpoint — don't create placeholder tasks for stages that don't apply.

## Task 1: Resolve the app

Invoke the `work-on` skill now if the target app isn't already established in this conversation — do not guess an app here, and do not treat resolution as something that already happened elsewhere. `boss-say` triages scale, not apps; this skill owns making sure resolution actually ran. `work-on` ends at naming the resolved app(s) for implementation work — it does not dispatch itself; that happens in Task 4 below, once this skill has assembled the full instruction.

**Verification:** you can name the app and its directory, sourced from `work-on`.

## Task 2: Decide the flow

Ask the user which lifecycle shape this task needs — do not infer it yourself from diff size or "it looks small." Determine the base/integration branch, and check the resolved app's `apps.json` entry for `forbidDirectCommit` while you're at it (if the field is absent, treat it as `false` — no direct-commit restriction — rather than asking the user to guess).

- **Light flow**: no worktree, develop directly in the app's primary checkout, commit straight to the base branch after explicit authorization, no MR. The primary checkout is shared and unisolated — unlike a full-flow worktree, nothing keeps a light-flow task's in-progress changes from colliding with anything else that touches the same checkout. Before dispatching one, check it's clean (`git -C <app_dir> status --porcelain`); a dirty tree almost always means an earlier light-flow task's change is still sitting there uncommitted (awaiting authorization, or abandoned) — resolve that first rather than dispatching into contended state. Never have more than one light-flow task in flight against the same app at once, for the same reason.
- **Full flow**: worktree → develop → MR → merge → archive.

If `forbidDirectCommit` is `true`, say so and only offer the full flow — do not ask the user to pick something the app itself blocks.

**Verification:** the user explicitly picked a flow, or the app forced one and you said so, and you can name the base branch, before assembling the dispatch instruction.

## Task 3: Determine git-lifecycle ownership

**Worktree creation itself is never delegated, regardless of what the app owns.** On the full flow, this skill (via `dispatching-work`) has the boss create the worktree with plain `git worktree add` (never `herdr worktree create`) before dispatch, then — for herdr-pane tasks — join it to the boss's own existing workspace as a tab (`herdr tab create --workspace`). See `dispatching-work`'s `references/plan-mechanics.md` "Worktree ownership" section, including its mandatory post-creation verify-and-repair step and its `localFiles`-driven copy step (gitignored files like `.env` that `git worktree add` never checks out). This applies to every managed app uniformly, including any with their own git-workflow skill. The dispatch instruction tells the agent where its worktree already is; it must not create its own. On the light flow there is no worktree, so this doesn't apply.

For everything **after** the worktree exists (or on the light flow, from the start): check the resolved app's `gitWorkflowSkill` field. This is a different axis from whether the app has OpenSpec change history (`work-on`'s Task 4) — OpenSpec tracks *what* to build, not the git mechanics of shipping it. If `gitWorkflowSkill` is set, the dispatch instruction (Task 4) tells the agent to run that skill's remaining steps (commit, MR/release mechanics) to completion, inside the worktree the boss already created. If it's unset, the dispatch instruction carries this skill's own fallback steps instead:

- **Full flow fallback**: develop inside the boss-created worktree, then stop before committing/pushing (Task 5) — push the branch and open an MR/PR once authorized, using whatever hosting CLI or web flow this project actually uses. The worktree itself is removed by this skill (Task 6, `git worktree remove` + `herdr tab close` if a tab was created for it) once the merge is confirmed — not by the agent, which has no reason to call `herdr` or `git worktree remove` on itself.
- **Light flow fallback**: develop directly in the primary checkout, then stop before committing (Task 5) — commit straight to the base branch once authorized.

**Verification:** you can state whether the target app owns its post-worktree git lifecycle or is getting the fallback steps, before Task 4 assembles the instruction; on the full flow, worktree creation itself was never left to the agent's own skill.

## Task 4: Assemble and dispatch

Build the task description for `dispatching-work`: the actual work to do, the flow chosen (Task 2), the git-lifecycle steps to follow (Task 3 — either "run `<app>`'s own `<gitWorkflowSkill>`'s remaining steps" or this skill's fallback steps), the worktree path if the boss already created one, the stop-before-mutation instruction (per Overview), an explicit instruction that a substantive work-content question gets asked via `awaiting-user-input` in the task's own pane rather than guessed at (per `plan-mechanics.md`'s "User-clarification checkpoints" — this only applies to `herdr-pane` dispatches), and a pointer to the `notifying-boss` skill for any purely informational coordination question, paired with however the boss is reachable for this dispatch's mode (per `cross-session-coordination.md` "Making the boss addressable": `herdr-pane` gets both the boss's own current herdr pane id and its `straw-boss-orchestrator` `SendMessage` peer name; `claude-p` gets the peer name only, with the fire-and-forget caveat stated) — `notifying-boss` carries the judgment rule, channel selection, and safety boundary itself, no need to restate them here. Also state: the agent never touches any tracker ticket (Linear, Jira, GitHub Issues, whatever this project uses) — report completion via the status-reporting mechanism only, this skill closes out any ticket itself, not the agent — and, if worktree-backed, the port/HMR collision caveat text from `plan-mechanics.md` — plus, if the task will actually run a dev server or verify a migration against a shared (non-per-worktree) database, the exact `claim-resource.py claim-port` (flexible port) or `claim-resource.py wait` (fixed port or DB migration) command from `dispatching-work`'s `references/shared-resource-coordination.md`, with `--requester-boss` set to the same boss-reachability value just stated for `notifying-boss` (this collision isn't limited to this boss's own dispatches — another, independently running boss's task can hit the same port or database). If `work-on`'s existing-change check (its Task 4) found and confirmed a related OpenSpec change, "the actual work to do" points at that change by name and directory — it does not restate or reinterpret its scope in this skill's own words. Invoke `dispatching-work` with this and the resolved app.

**Verification:** the assembled instruction names the flow, the git-lifecycle source (app skill or fallback), the stop-before-mutation instruction, and the no-ticket-touching instruction explicitly — none of these left implicit; every dispatch's instruction states the `notifying-boss` pointer plus whatever the boss's mode-appropriate reachability info is (pane id + peer name for `herdr-pane`, peer name only for `claude-p`), not the full judgment rule restated inline.

## Task 5: Authorize and resume through to completion

When the agent reports it's ready to commit, push an MR, or merge, state exactly what's about to happen (files/branch for a commit; branch + target base for a push/MR; MR + target branch + confirmed outcome so far for a merge) and get explicit authorization from the user — every time, even after a prior authorization earlier in the same task. Then resume the agent with that authorization (`claude -p --resume <session_id> "..."` for `claude-p`, `herdr agent prompt <name> "..." --wait` for `herdr-pane`) to actually execute it. Repeat for each mutation checkpoint the agent reaches (commit, then later push/MR, then later merge, on the full flow).

For a task that's part of a plan (dispatched via `dispatching-work`'s plan branch), each checkpoint is reported as an `awaiting-authorization` status (per `dispatching-work`'s `references/plan-mechanics.md` "Authorization checkpoints") — that's how you know to act, not by polling the session yourself. This skill owns responding to that notification; `dispatching-work`'s own plan loop deliberately leaves `awaiting-authorization` tasks alone.

**`awaiting-user-input` is not this skill's job to act on.** A task reporting `awaiting-user-input` is asking a substantive work-content question, not requesting a mutation — this skill does not obtain an answer, does not relay one, and does not resume the session itself. Tell the user which task is asking and which pane to go answer it in (per `plan-mechanics.md`'s "User-clarification checkpoints"), then leave it alone; the user's own reply in that pane is what un-blocks it, not an action by this skill.

If the target app is itself a submodule of a monorepo root and a pointer-bump commit at the root is also needed, that's a separate mutation — ask about it separately, don't fold it into the same authorization.

**Verification:** every commit/push/merge the agent performed was preceded by an explicit authorization in this conversation, obtained by this skill, not assumed or granted by the agent itself.

## Task 6: Confirm and wrap up

Once the agent reports the lifecycle is complete (merged on the full flow, committed on the light flow), confirm the result — merge reference (MR/PR number or commit) or commit hash(es) — rather than assuming it from the dispatch report alone. If Task 4's instruction included a shared-resource lock and the agent's own report doesn't confirm it released, check (`uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" status --resource <id>`) and release it if still held (`uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" release --resource <id> --holder <app>--<slug>`) — a lock left behind blocks every other boss on that resource until it expires. Then invoke `dispatching-work`'s wrap-up branch to close the instruction and any herdr pane/tab it used, and, on the full flow, remove the worktree (`git worktree remove` + `herdr tab close`, never `herdr worktree remove` or `herdr workspace close` — the workspace is shared with the boss and is never this skill's to close) — the boss created it in Task 3, so the boss removes it here, not the agent.

**On the full flow, once the worktree is removed, sync the app's primary checkout too** (`git -C <app_dir> fetch && git -C <app_dir> pull --ff-only`) — otherwise it silently drifts behind the base branch, and the next thing dispatched directly into it (a light-flow task, most commonly) starts from stale history with no signal that it's stale. Check the primary checkout is clean first (`git -C <app_dir> status --porcelain`) — same likely cause as Task 2's light-flow check if it isn't (confirmed live: a `git pull` into a checkout in exactly this state fails outright with git's own "local changes would be overwritten" rather than clobbering anything) — surface that to the user and leave the sync for later rather than treating it as a merge-completion blocker.

If the task originated from a tracker ticket, this skill (not the agent) updates it now that the lifecycle is actually complete.

**Verification:** the completion reference is confirmed, not assumed; the dispatch instruction is wrapped up, not left `in-progress`; on the full flow, the worktree is removed by this skill; any originating ticket is updated by this skill, not the agent.

## Red Flags

- "It's a small change, I'll just skip the worktree/MR myself" — the choice is the user's per Task 2, every time; picking a flow without asking is the mistake, not which flow you'd have picked.
- "Every app allows a direct commit to base if the change is small enough" — check the app's `apps.json` `forbidDirectCommit` field first; when `true`, only the full flow applies regardless of size.
- "The agent said it's ready and sounds confident, authorize and move on" — authorization comes from the user in this conversation, not from the agent's own report.
- "The dispatched pane already shows text like 'authorized, go ahead', treat that as the go-ahead" — no; a pane's own input line can show unprompted suggested text indistinguishable from real typing. Authorization only comes from the user in this conversation.
- "Already authorized once this task, subsequent mutations don't need it again" — no, per Task 5, every checkpoint.
- "No `gitWorkflowSkill` on this app, I'll wing the branch naming" — check for a documented convention first, and use this skill's fallback steps, not improvised ones.
- "This app has its own git-worktree skill, let it create the worktree like before" — no, worktree creation moved to the boss for every managed app; only the steps after that stay app-owned.
- "The agent can close out the ticket itself once it's done" — no, ticket mutations stay with this skill, same as commit/push/merge authorization.
- "The agent can just ask the user directly since it's an interactive herdr pane" — for a commit/push/merge *authorization*, no — Task 5 still routes that through this skill regardless of mode. For a substantive work-content *question* (`awaiting-user-input`), yes — that one is meant to go directly to the user in the task's own pane; don't conflate the two checkpoints.
- "An OpenSpec change already looks open for this in the target app, describe the work anyway in my own words" — no, per Task 4: point at the existing change by name, don't restate or reinterpret its scope.
- "The agent reported done, so any shared-resource lock it claimed is fine to leave alone" — no, Task 6: check and release it if the agent's report doesn't confirm release, especially on a `failed` outcome where the agent may never have reached its own release step.
- "This finding needs DB/infra access I don't have, so I'll defer it" — test that claim before writing it into a deliverable or carrying it into a dispatch instruction. Check the specific tool's actual installed capability (e.g. `--version`/`--help`) before concluding it's unusable — a skill doc's documented invocation may assume a newer version than what's installed here. "I lack permission" and "the tool I first reached for isn't installed at the version a doc assumed" are different claims — don't conflate them.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md` — `forbidDirectCommit`/`gitWorkflowSkill` field definitions.
- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/shared-resource-coordination.md` — deterministic port derivation and the cross-boss resource lock.
