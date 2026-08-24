## Why

`shipping-task`'s full flow currently stops for user authorization twice — once before push (opening an MR/PR) and once before merge — but the worktree and feature branch a push targets are always created by the main agent itself before dispatch (`shipping-task`'s Task 3: "Worktree creation itself is never delegated"). The branch's existence and scope are already implicitly authorized the moment the main agent set it up for this task; pushing it and opening an MR doesn't touch the shared target branch's history and is as reversible as the commits already sitting in the worktree. The moment that actually needs a human's judgment is merge — where the change actually lands in the shared branch. Requiring a second authorization just to publish a branch the user already agreed to work on is friction without a matching safety benefit.

## What Changes

- `shipping-task`'s full flow drops the push/MR authorization checkpoint. Only merge remains a stop-and-wait-for-authorization checkpoint.
- A dispatched agent pushes and opens an MR/PR on its own once ready, and pushes further updates to the same branch on its own (e.g. addressing review feedback) — no authorization needed for any of it.
- **The exemption is scoped to the task's own feature branch only** — the one the main agent's own worktree was created for. A push that lands on or updates any other tracked branch (the target/base branch directly, a monorepo root's submodule pointer-bump once the app's commit lands, a version-bump/release-tag push an app-owned `gitWorkflowSkill`'s remaining steps might perform against a protected/base branch) is not covered — it never touched the "already-authorized the moment the branch was created" reasoning above, and keeps its existing authorization gate unchanged.
- Once pushed, the agent sends a non-blocking notification through the recorded main-agent herdr pane (branch name, MR/PR reference) and continues immediately. `SendMessage` is only a Claude-to-Claude fallback; a progress record covers the no-live-route case.
- This is a universal default — applies to every managed app uniformly, no per-app override (confirmed with the user: not worth the config surface for now).
- `docs/roles.md`'s "Autonomy boundary" absolute-gates line narrows to merge only — push isn't an authority the main agent is now permitted to bypass; it simply isn't a gate anymore.
- `shipping-task` Task 5 narrows to merge authorization; gains a short branch for handling the new push-FYI notification (relay to the user, no action, no resume).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `dispatch-authority`: the "Authorization gates remain absolute" requirement narrows from "push or merge" to merge only — pushing the task's own feature branch is no longer a gate the main agent's autonomy could ever have bypassed, because it no longer requires authorization to begin with. A push to any other tracked branch is untouched by this narrowing.
- `dispatch-completion-reporting`: the live notification requirement no longer treats a feature-branch push as a stop-before-mutation checkpoint; a separate non-blocking FYI-and-continue pattern remains distinct from stop-and-wait semantics.
- `dispatched-agent-escalation`: the "Authorization escalation is unaffected" requirement's "push/merge authorization gate" label narrows to merge and any push outside the task's own feature branch — found during apply via a repo-wide grep for stale "push/merge" wording, not in the original proposal.

## Impact

- `skills/shipping-task/SKILL.md` — Overview, Task 3 (full-flow fallback steps, and the `gitWorkflowSkill`-owned "remaining steps... to completion" sentence — that phrase itself must carry the feature-branch scope, not just the fallback path), Task 4 (dispatch-instruction assembly text), Task 5 (retitled/narrowed to merge authorization, new push-FYI handling branch), Red Flags, Verification lines that currently say "push/merge."
- `docs/roles.md` — "Autonomy boundary" section's absolute-gates sentence.
- `.claude-plugin/plugin.json` — the description's "an authorization gate on every push/merge" claim, now inaccurate for a feature-branch push; narrow to merge (and any push outside the task's own feature branch).
- `openspec/specs/dispatch-authority/spec.md`, `openspec/specs/dispatch-completion-reporting/spec.md`, `openspec/specs/dispatched-agent-escalation/spec.md` — requirement deltas.
- **Found during apply, via a repo-wide grep for "push/merge"/"push or merge"/"ready to push"/"awaiting-authorization" — not in the original proposal:**
  - `skills/i-am-orchestrator/SKILL.md` — the SessionStart priming text's `awaiting-authorization` description (most-read statement of this rule in the plugin).
  - `skills/dispatching-work/SKILL.md` — the checkpoint/report types table (row scope, new push-FYI row, "Five" → "Six"), the escalation-order paragraph's "push/merge readiness gate" phrase.
  - `skills/dispatching-work/references/plan-mechanics.md` — "Authorization checkpoints" section (scope, example note), "User-clarification checkpoints" section's "push/merge decision" phrase.
  - `skills/dispatching-work/references/dispatch-mechanics.md` — the `claude-p` checkpoint-detection paragraphs, which assumed a push always stops the agent.
  - `skills/notifying-main-agent/SKILL.md` — no branch previously covered a report-and-continue push; a worker following the existing "done/failed/checkpoint" mechanism literally would have written an invalid status value or waited like a checkpoint. Added a third branch, "Report a completed push, then continue," plus frontmatter/entry-condition/Red-Flags updates.
  - `docs/architecture.md`, `README.md`, `README.zh-TW.md`, `CONTEXT.md` — user-facing descriptions of the same "push/merge" gate.
  - `skills/boss-say/SKILL.md` — a real gap found on a second advisor pass (the first grep used `push and merge` instead of `push/merge` and missed it): the batch path drives full-flow git-lifecycle checkpoints itself (never through `shipping-task`), and had no branch for the provider-specific push FYI, which intentionally has no Plan-status watcher event. Added Task 5 step 7, renumbered the old step 7 to step 8, and fixed every cross-reference the renumber broke.

Explicitly out of scope: a per-app override to keep push authorization for a specific app (confirmed with the user — universal default only, no new `apps.json` field); any change to commit's existing no-authorization behavior; any change to the light flow (no push/merge checkpoint there today, none added); this project's own global force-push confirmation rule (`~/.claude/rules/git-safety.md`) — unrelated, a different operation from a normal branch push; `shipping-task` Task 5's existing monorepo-root submodule pointer-bump line ("that's a separate mutation — ask about it separately") — unchanged, since that push lands on the root's own tracked branch, not the task's feature branch, and stays gated under the scoping above; any release/version-bump push an app-owned `gitWorkflowSkill` might perform against a protected/base branch — same reasoning, unchanged.
