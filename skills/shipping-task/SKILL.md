---
name: shipping-task
description: Carries one task through a standardized git lifecycle in one of the project's managed apps. Use when starting or continuing implementation work on a single task, e.g. "work on this", "let's implement this in <app>". Not for scoping/planning the task (your project's task-scoping skill), picking the app (`work-on`, invoked internally here), or many independent tasks at once (`boss-say`).
---

## Overview

straw-boss standardizes two lifecycle shapes across every managed app: a **full flow** (worktree → develop → MR → merge → archive) for changes with real size or risk, and a **light flow** (develop directly in the app's primary checkout, commit straight to the base branch) for small, mechanical, low-risk changes — a one-line prop, a config value, a typo fix. Which shape applies is not this skill's call to make silently: Task 2 asks the user, except where the resolved app's `apps.json` entry sets `forbidDirectCommit: true`, in which case only the full flow is offered. Scoping the task happens before this skill. Picking the app happens as this skill's own first step, via `work-on`.

The work itself happens in a session dispatched into the target app (`dispatching-work`), not in this session. An app may already have its own worktree/release tooling — check its `apps.json` entry's `gitWorkflowSkill` field. When it's set, the dispatch instruction tells the dispatched session to run that skill to completion, and this skill only confirms the outcome. Where an app has none, this skill's own fallback steps below travel in the dispatch instruction instead.

**Commit/push/merge are external mutations, and the dispatched session cannot self-authorize them** — every dispatch instruction this skill assembles explicitly tells the dispatched session to stop and report back once it's ready to commit/push/merge, not execute it. This skill (interactive with the actual user) obtains authorization and resumes the dispatched session to proceed. This holds for both dispatch modes and regardless of which app owns its own git-workflow skill.

## Task Initialization

This spans many turns — dispatch now, develop over an unknown number of turns inside the dispatched session, authorize the mutation possibly much later. Track it with TaskCreate, one task per stage, so progress survives context compaction or a session resume. On the light flow, most stages collapse to a single commit checkpoint — don't create placeholder tasks for stages that don't apply.

## Task 1: Resolve the app

Invoke the `work-on` skill now if the target app isn't already established in this conversation — do not guess an app here, and do not treat resolution as something that already happened elsewhere. This skill is a primary entry point; it owns making sure resolution actually ran. `work-on` ends at naming the resolved app(s) for implementation work — it does not dispatch itself; that happens in Task 4 below, once this skill has assembled the full instruction.

**Verification:** you can name the app and its directory, sourced from `work-on`.

## Task 2: Decide the flow

Ask the user which lifecycle shape this task needs — do not infer it yourself from diff size or "it looks small." Determine the base/integration branch, and check the resolved app's `apps.json` entry for `forbidDirectCommit` while you're at it (if the field is absent, treat it as `false` — no direct-commit restriction — rather than asking the user to guess).

- **Light flow**: no worktree, develop directly in the app's primary checkout, commit straight to the base branch after explicit authorization, no MR.
- **Full flow**: worktree → develop → MR → merge → archive.

If `forbidDirectCommit` is `true`, say so and only offer the full flow — do not ask the user to pick something the app itself blocks.

**Verification:** the user explicitly picked a flow, or the app forced one and you said so, and you can name the base branch, before assembling the dispatch instruction.

## Task 3: Determine git-lifecycle ownership

**Worktree creation itself is never delegated, regardless of what the app owns.** On the full flow, this skill (via `dispatching-work`) has the orchestrator create the worktree with plain `git worktree add` (never `herdr worktree create` — it always opens a new herdr workspace with no way to target an existing one) before dispatch, then — for herdr-pane tasks — join it to the orchestrator's own existing workspace as a tab (`herdr tab create --workspace`). See `dispatching-work`'s `references/plan-mechanics.md` "Worktree ownership" section, including its mandatory post-creation verify-and-repair step and its `localFiles`-driven copy step (gitignored files like `.env` that `git worktree add` never checks out). This applies to every managed app uniformly, including any with their own git-workflow skill. The dispatch instruction tells the dispatched session where its worktree already is; it must not create its own. On the light flow there is no worktree, so this doesn't apply.

For everything **after** the worktree exists (or on the light flow, from the start): check the resolved app's `gitWorkflowSkill` field. This is a different axis from whether the app has OpenSpec change history (`work-on`'s Task 4) — OpenSpec tracks *what* to build, not the git mechanics of shipping it. If `gitWorkflowSkill` is set, the dispatch instruction (Task 4) tells the dispatched session to run that skill's remaining steps (commit, MR/release mechanics) to completion, inside the worktree the orchestrator already created. If it's unset, the dispatch instruction carries this skill's own fallback steps instead:

- **Full flow fallback**: develop inside the orchestrator-created worktree, then stop before committing/pushing (Task 5) — push the branch and open an MR/PR once authorized, using whatever hosting CLI or web flow this project actually uses. The worktree itself is removed by this skill (Task 6, `git worktree remove` + `herdr tab close` if a tab was created for it) once the merge is confirmed — not by the dispatched session, which has no reason to call `herdr` or `git worktree remove` on itself.
- **Light flow fallback**: develop directly in the primary checkout, then stop before committing (Task 5) — commit straight to the base branch once authorized.

**Verification:** you can state whether the target app owns its post-worktree git lifecycle or is getting the fallback steps, before Task 4 assembles the instruction; on the full flow, worktree creation itself was never left to the dispatched session's own skill.

## Task 4: Assemble and dispatch

Build the task description for `dispatching-work`: the actual work to do, the flow chosen (Task 2), the git-lifecycle steps to follow (Task 3 — either "run `<app>`'s own `<gitWorkflowSkill>`'s remaining steps" or this skill's fallback steps), the worktree path if the orchestrator already created one, an explicit, unambiguous instruction that any commit/push/merge must stop and report readiness rather than execute (this skill will obtain authorization and resume), an explicit instruction that a substantive work-content question gets asked via `awaiting-user-input` in the task's own pane rather than guessed at (per `plan-mechanics.md`'s "User-clarification checkpoints" — this only applies to `herdr-pane` dispatches), and — for `herdr-pane` dispatches only — the orchestrator's peer name plus a pointer to the `notifying-boss` skill for any purely informational coordination question (`straw-boss-orchestrator`, per `cross-session-coordination.md` "Making the orchestrator addressable" — that skill carries the judgment rule and safety boundary itself, no need to restate them here). Also state: the dispatched session never touches any tracker ticket (Linear, Jira, GitHub Issues, whatever this project uses) — report completion via the status-reporting mechanism only, this skill closes out any ticket itself, not the dispatched session — and, if worktree-backed, the port/HMR collision caveat text from `plan-mechanics.md`. If `work-on`'s existing-change check (its Task 4) found and confirmed a related OpenSpec change, "the actual work to do" points at that change by name and directory — it does not restate or reinterpret its scope in this skill's own words. Invoke `dispatching-work` with this and the resolved app.

**Verification:** the assembled instruction names the flow, the git-lifecycle source (app skill or fallback), the stop-before-mutation instruction, and the no-ticket-touching instruction explicitly — none of these left implicit; for `herdr-pane` dispatches, the instruction also states the orchestrator's peer name and the `notifying-boss` pointer, not the full judgment rule restated inline.

## Task 5: Authorize and resume through to completion

When the dispatched session reports it's ready to commit, push an MR, or merge, state exactly what's about to happen (files/branch for a commit; branch + target base for a push/MR; MR + target branch + confirmed outcome so far for a merge) and get explicit authorization from the user — every time, even after a prior authorization earlier in the same task. Then resume the dispatched session with that authorization (`claude -p --resume <session_id> "..."` for `claude-p`, `herdr agent prompt <name> "..." --wait` for `herdr-pane`) to actually execute it. Repeat for each mutation checkpoint the dispatched session reaches (commit, then later push/MR, then later merge, on the full flow).

For a task that's part of a plan (dispatched via `dispatching-work`'s plan branch), each checkpoint is reported as an `awaiting-authorization` status (per `dispatching-work`'s `references/plan-mechanics.md` "Authorization checkpoints") — that's how you know to act, not by polling the session yourself. This skill owns responding to that notification; `dispatching-work`'s own plan loop deliberately leaves `awaiting-authorization` tasks alone.

**`awaiting-user-input` is not this skill's job to act on.** A task reporting `awaiting-user-input` is asking a substantive work-content question, not requesting a mutation — this skill does not obtain an answer, does not relay one, and does not resume the session itself. Tell the user which task is asking and which pane to go answer it in (per `plan-mechanics.md`'s "User-clarification checkpoints"), then leave it alone; the user's own reply in that pane is what un-blocks it, not an action by this skill.

If the target app is itself a submodule of a monorepo root and a pointer-bump commit at the root is also needed, that's a separate mutation — ask about it separately, don't fold it into the same authorization.

**Verification:** every commit/push/merge the dispatched session performed was preceded by an explicit authorization in this conversation, obtained by this skill, not assumed or granted by the dispatched session itself.

## Task 6: Confirm and wrap up

Once the dispatched session reports the lifecycle is complete (merged on the full flow, committed on the light flow), confirm the result — merge reference (MR/PR number or commit) or commit hash(es) — rather than assuming it from the dispatch report alone. Then invoke `dispatching-work`'s wrap-up branch to close the instruction and any herdr pane/tab it used, and, on the full flow, remove the worktree (`git worktree remove` + `herdr tab close`, never `herdr worktree remove` or `herdr workspace close` — the workspace is shared with the orchestrator and is never this skill's to close) — the orchestrator created it in Task 3, so the orchestrator removes it here, not the dispatched session.

If the task originated from a tracker ticket, this skill (not the dispatched session) updates it now that the lifecycle is actually complete.

**Verification:** the completion reference is confirmed, not assumed; the dispatch instruction is wrapped up, not left `in-progress`; on the full flow, the worktree is removed by this skill; any originating ticket is updated by this skill, not the dispatched session.

## Red Flags

- "It's a small change, I'll just skip the worktree/MR myself" — the choice is the user's per Task 2, every time; picking a flow without asking is the mistake, not which flow you'd have picked.
- "Every app allows a direct commit to base if the change is small enough" — check the app's `apps.json` `forbidDirectCommit` field first; when `true`, only the full flow applies regardless of size.
- "The dispatched session said it's ready and sounds confident, authorize and move on" — authorization comes from the user in this conversation, not from the dispatched session's own report.
- "Already authorized once this task, subsequent mutations don't need it again" — no, per Task 5, every checkpoint.
- "No `gitWorkflowSkill` on this app, I'll wing the branch naming" — check for a documented convention first, and use this skill's fallback steps, not improvised ones.
- "This app has its own git-worktree skill, let it create the worktree like before" — no, worktree creation moved to the orchestrator for every managed app; only the steps after that stay app-owned.
- "The dispatched session can close out the ticket itself once it's done" — no, ticket mutations stay with this skill, same as commit/push/merge authorization.
- "The dispatched session can just ask the user directly since it's an interactive herdr pane" — for a commit/push/merge *authorization*, no — Task 5 still routes that through this skill regardless of mode. For a substantive work-content *question* (`awaiting-user-input`), yes — that one is meant to go directly to the user in the task's own pane; don't conflate the two checkpoints.
- "An OpenSpec change already looks open for this in the target app, describe the work anyway in my own words" — no, per Task 4: point at the existing change by name, don't restate or reinterpret its scope.
- "This finding needs DB/infra access I don't have, so I'll defer it" — test that claim before writing it into a deliverable or carrying it into a dispatch instruction. Check the specific tool's actual installed capability (e.g. `--version`/`--help`) before concluding it's unusable — a skill doc's documented invocation may assume a newer version than what's installed here. "I lack permission" and "the tool I first reached for isn't installed at the version a doc assumed" are different claims — don't conflate them.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md` — `forbidDirectCommit`/`gitWorkflowSkill` field definitions.
