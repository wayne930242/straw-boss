## Context

See `proposal.md` - Why for motivation. Relevant current state:

- `shipping-task`'s full flow originally stopped for authorization twice: once before push and once before merge. Both used the same stop-and-report shape; the current transport refinement reports live through herdr and reserves `SendMessage` for Claude-to-Claude fallback.
- The worktree and feature branch a push targets are always created by the main agent itself, before dispatch, for every full-flow task uniformly (`shipping-task`'s Task 3, `dispatching-work`'s `plan-mechanics.md` "Worktree ownership") — never left to the dispatched agent. There is no scenario where a push authorization checkpoint is guarding a branch the main agent didn't already set up for this exact task.
- `shipping-task`'s existing checkpoint-handling already distinguishes three patterns by how `shipping-task` responds: `awaiting-authorization` (this skill's job, blocking — obtain authorization, resume), `awaiting-user-input` (not this skill's job — relay to the user's pane, don't act), `awaiting-main-agent` (this skill's job, blocking — resolve directly via `reply-to-worker.py`). This change adds a fourth pattern with different semantics from all three: this skill's job, but *non-blocking*.

## Goals / Non-Goals

**Goals:**
- Drop the push/MR authorization checkpoint from the full flow, **scoped to the task's own feature branch only**; merge remains the only stop-and-wait mutation gate for that branch.
- The dispatched agent still reports every push (and subsequent push to the same branch/MR) to the main agent — required, not optional — but as a fire-and-continue notification, never a stop.
- Reuse the existing informational notification shape; no new status value is needed — only the "does the agent then wait" behavior changes. The push FYI never gets a status-file write or enters `VALID_STATUSES`; it uses herdr when recorded, Claude-to-Claude `SendMessage` fallback, or a progress record with no live route.
- Apply uniformly to every managed app — no new `apps.json` field (confirmed with the user).

**Non-Goals:**
- No per-app override to keep push authorization for a specific app.
- No change to commit's existing no-authorization behavior.
- No change to the light flow (no push/merge checkpoint there today; none added).
- No change to this project's global force-push confirmation rule (`~/.claude/rules/git-safety.md`) — a different, more dangerous operation (rewrites history) than a normal branch push, unaffected by this change.
- No retroactive handling for a task already mid-flight under the old policy (see Migration Plan) — its own dispatch instruction was written before this change and still says what it said.

## Decisions

### The exemption is scoped to the task's own feature branch, not "any push"
The Why's rationale ("push doesn't touch the shared target branch's history") only holds for the branch the main agent's own worktree was created for. Two existing paths in `shipping-task` push to a *different* tracked branch and don't share that rationale:
- Task 5's existing monorepo-root submodule pointer-bump line — that push lands on the root repo's own tracked branch once the submodule's commit lands, not the task's feature branch.
- An app-owned `gitWorkflowSkill`'s "remaining steps... to completion" (Task 3) can include release mechanics — a version-bump push, a release-tag push — that may target a protected/base branch rather than the feature branch.

Both keep their existing authorization gate, unchanged by this proposal. The discriminating test carried into every edited file: does this push land on or modify a branch other than the task's own feature branch? If yes, it's still gated. This scoping was not in the original ask but is required for the stated rationale to hold — without it, the new prose would silently exempt pushes the rationale never covered.
**Alternative considered:** state the exemption as "any push the fallback steps perform" and leave `gitWorkflowSkill`/submodule paths to the reader's judgment. Rejected — the codebase's own convention (explicit, non-improvised checkpoint wording, per the first change's `awaiting-main-agent` work) argues against leaving a safety-relevant distinction implicit.

### The push notification reuses the existing live FYI shape, minus the wait
The agent sends the same self-identifying FYI through the primary herdr route, naming the branch and MR/PR reference. Only a Claude-to-Claude pair may fall back to `SendMessage`; no provider waits for a reply afterward.
**Alternative considered:** use `report-progress.py` (the passive, non-notifying log) instead of an active push. Rejected — the user explicitly wants the main agent to actually surface this to them, not just have it be discoverable on demand via `peeking-work`; a passive log entry could sit unnoticed indefinitely, defeating the point of "FYI."

### Report after the push completes, not before as an announcement of intent
Unlike the old stop-before-mutation pattern (report readiness, then wait to be told to proceed), there's no gate to wait through here — the agent pushes on its own authority immediately. Reporting *after*, with the real branch/MR reference, gives the main agent something concrete and actionable (a link) instead of a content-free "about to push" notice.

### Dispatch-instruction wording must clearly distinguish "stop and wait" from "report and continue"
Both notifications are assembled by the same skill but mean opposite things for what the agent does next. Merge keeps stop-and-wait phrasing; a feature-branch push says report through the available route, then keep working.
**Why this matters:** the codebase's own established convention (`dispatching-work`'s "Four checkpoint/report types" table, extended for `awaiting-main-agent`) already treats "which of several push types is this" as something that needs unambiguous, explicit labeling in the instruction text, not left to the agent's own inference — the same discipline applies to this fourth pattern.

### `notifying-main-agent` gets a third top-level branch for the push notification, not folded into "Report own status"
Found during apply: the status branch mandates an enumerated `VALID_STATUSES` value and a stop/report entry condition. A feature-branch FYI satisfies neither, so the dedicated "Report a completed push, then continue" branch skips the status write, uses the available herdr/Claude-to-Claude fallback/progress route, and states "continue immediately."

### `shipping-task` Task 5 gets a distinct branch for the push notification, following the shape already established for the other three patterns
`awaiting-authorization` → this skill acts, blocking. `awaiting-user-input` → not this skill's job, no action. `awaiting-main-agent` → this skill acts, blocking, via `reply-to-worker.py`. Push notification → this skill acts (relay to the user), but *non-blocking* — no authorization to obtain, no session to resume, because the agent was never waiting. Naming this as its own branch (rather than folding it into the merge-authorization branch) keeps the pattern explicit and matches how the codebase already prefers a named branch per distinct response shape over an implicit catch-all.

## Risks / Trade-offs

- **[Trade-off] This narrows an authorization surface the project has otherwise treated as absolute** → Accepted, per explicit user direction, and bounded specifically to a push that stays on the task's own feature branch — an action that never touches the shared target branch's history and was already reachable with no gate at all before this project's own `awaiting-authorization` checkpoint existed for it. Merge, the actual point changes land in the shared branch, is untouched — as is any push to a branch other than the task's own (see "The exemption is scoped..." decision above).
- **[Risk] The scoped exemption could be misread as "push needs no authorization" during apply, silently absorbing the submodule-pointer-bump and app-owned-release-push cases** → Mitigation: every edited file states the feature-branch scoping explicitly rather than saying "push" unqualified (see decision above); `shipping-task` Task 5's existing submodule line is explicitly called out as unchanged in `proposal.md`'s Impact section, and Task 4's instruction-assembly wording names the scope, not just "push."
- **[Risk] An agent might still stop and wait after push out of habit or instruction ambiguity** → Mitigation: distinctly-worded instruction text (decision above) plus a new Red Flag in `shipping-task` calling out the conflation explicitly.
- **[Risk] The FYI notification could go unnoticed while the main agent is busy** → The recorded herdr pane is the primary queue; a progress record keeps the FYI discoverable when no live route exists. `shipping-task` still relays it once observed.
- **[Risk] A badly-formed or premature push could still happen without a human ever reviewing it before it exists** → Mitigation: not materially different from today's status quo, where commits already happen with zero authorization gate and already reach the remote worktree/branch unreviewed; the push only publishes a branch scoped to this exact task, never touches the target branch, and merge's unchanged authorization gate still catches it before anything lands in shared history.
- **[Risk] The proposal's original file list undercounted every place that states "push/merge" as a unit** → Materialized during apply: a repo-wide grep after the initially-scoped edits turned up nine more real hits, including the SessionStart priming skill (`i-am-orchestrator`) — the most-read statement of the authorization rule in the whole plugin — and `notifying-main-agent`'s reporting mechanism, which had no branch a worker could correctly use for a report-and-continue push at all. Mitigation: the grep is now part of task group 6 below, so a future re-run of this change (or a similar scope-narrowing change) repeats it rather than trusting the original Impact list.
- **[Risk] The batch path (`boss-say`) drives full-flow git-lifecycle checkpoints itself, bypassing `shipping-task` entirely, and the first grep's exact search terms missed it** → Materialized on a second advisor pass: the grep used `push and merge` where it should have used `push/merge`, so `awaiting-authorization` (the status name alone, no literal word "push" on the same line) never got searched, and `boss-say`'s Task 5 — which has its own independent status-handling steps, not a call into `shipping-task` — had no step for the push-FYI at all. Mitigation: task group 7 adds the step and fixes the renumbering it forced; recorded here so a similar future change greps status names too, not just the mutation-noun wording.

## Migration Plan

Purely a policy/prose change — no schema, no script, no status-value change. A task already mid-flight and currently stopped at the old push-authorization checkpoint keeps working exactly as before: its own dispatch instruction was assembled under the old policy and still says to stop and wait, so `shipping-task` Task 5 still authorizes and resumes it once, the normal way — no special handling, no retroactive resume-without-authorization. Only dispatch instructions assembled *after* this change carries the new push-FYI wording. Rollback is a plain revert of the prose/spec changes; nothing about `done`/`failed`/`awaiting-*`/merge-authorization behavior changes, so reverting cannot leave an in-flight task's state inconsistent.
