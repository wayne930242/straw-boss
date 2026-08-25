# Plan mechanics

Exact file formats, scripts, and command sequences for plan-aware dispatch. Extends `dispatch-mechanics.md` (single-instruction dispatch is unchanged and still the mechanism each plan task ultimately uses) — read that file too, this one only covers what's new for plans. `<app_dir>` below is defined there ("Resolving the app directory") — never assume it looks like `<repo_root>/apps/<app>`.

## Plan file

`<home>/.straw-boss/plans/<plan-slug>/plan.json`. Written once by `work-on` after the decomposition is confirmed with the user via `grilling`; afterward only the main agent updates per-task `status` fields — never a dispatched agent's own session.

```json
{
  "plan_id": "p-<slug>",
  "created_at": "2026-08-16T10:00:00+08:00",
  "status": "planning",
  "tasks": [
    {
      "task_id": "t1",
      "app": "api",
      "description": "One high-level sentence — what, not how. No detailed spec here.",
      "depends_on": [],
      "status": "planned"
    },
    {
      "task_id": "t2",
      "app": "web",
      "description": "...",
      "depends_on": ["t1"],
      "status": "planned"
    }
  ]
}
```

`plan.status`: `planning` (being confirmed) → `in-progress` (at least one task dispatched) → `done` (every task terminal: `done`/`failed`/`cancelled`). Each `tasks[].status`: `planned` → `dispatched` → `done`/`failed`/`cancelled`. A task's `depends_on` lists other `task_id`s in the same plan — empty means it's part of the first ready wave.

## Cross-task artifacts (when a dependent task needs its prerequisite's output)

A `depends_on` edge is only meaningful if the dependent task can actually get at what its prerequisite produced — `plan.json`'s `description` field is high-level prose, not a place to point at a file. Use `<home>/.straw-boss/plans/<plan-slug>/artifacts/` (a sibling of `status/`, created the same way — empty directory at plan-write time) for any file one task's output and a later task's input both need to reference. Name files `<task-id>-<short-label>.<ext>` so origin is obvious without cross-referencing `plan.json`. State the exact path in both tasks' dispatch instructions explicitly — the producing task's instruction says where to write it, the consuming task's instruction says where to read it from and that it's real required input, not optional context. Confirmed live: a dependent task's agent correctly treated a prerequisite's artifact file as authoritative input and produced output that genuinely depended on its content.

## Status directory (per-task completion reports)

`<home>/.straw-boss/plans/<plan-slug>/status/<task-id>.json`, created empty (directory only) when the plan is written, populated one file per task as each one finishes. Single-writer: only the dispatched task with that `task_id` ever writes its own file.

```json
{"status": "done", "note": "optional free text", "timestamp": "2026-08-16T10:30:00+08:00"}
```
or
```json
{"status": "failed", "note": "what went wrong, and whether it looks like a permission denial", "timestamp": "..."}
```
or, for a full-flow task that reached a merge or other-branch-push checkpoint (see "Authorization checkpoints" below):
```json
{"status": "awaiting-authorization", "note": "what it's ready to do -- e.g. \"ready to merge branch fix-foo into main\"", "timestamp": "..."}
```
or, for a task that hit a substantive work-content question, not a git mutation (see "User-clarification checkpoints" below):
```json
{"status": "awaiting-user-input", "note": "the question it's asking -- e.g. \"which of two existing approaches should this follow?\"", "timestamp": "..."}
```
or, for a task the main agent ended because the dispatch itself was wrong, not the agent's execution of it (see `docs/roles.md`'s Cancel; mechanics in `cross-session-coordination.md`):
```json
{"status": "cancelled", "note": "why the dispatch itself was wrong, not what the agent did", "timestamp": "..."}
```
`cancelled` is written by the main agent itself, never the dispatched task -- the only status value in this file with that property, since every other value is the dispatched task reporting on itself.

`awaiting-authorization`, `awaiting-user-input`, and `awaiting-main-agent` are all not terminal — the task's own `plan.json` entry stays `dispatched`, none joins or leaves the ready wave. All three exist so `watch-plan-status.py` can emit the checkpoint the same way it emits `done`/`failed`, instead of a task sitting silently idle with no signal that it's actually waiting on someone.

## Authorization checkpoints (full flow only)

An agent must stop and report readiness rather than execute a merge, or a push landing outside its own feature branch (a monorepo-root submodule pointer-bump, an app-owned git-workflow skill's protected-branch release push) — the main agent (in practice, `shipping-task`, not `dispatching-work` itself) obtains authorization and resumes it. Commit, and a push of the task's own feature branch, need no authorization and reach no checkpoint here; every interactive provider reports that FYI through the recorded main-agent herdr pane, with `report-progress.py` as the durable fallback. The generated contract supplies `awaiting-authorization` and its status command; the task brief states only a material task-specific authorization boundary that is not already present in the target project's instructions.

`dispatching-work`'s own plan-dispatch loop (wave computation, parallel dispatch, auto-detach) treats `awaiting-authorization` as "leave this task alone, it isn't terminal yet" — it does **not** attempt to authorize or resume it. That's `shipping-task`'s job (or whichever caller assembled the instruction and owns the authorization gate for it), watching the same status events and, on an `awaiting-authorization` event for one of its tasks, stating what's about to happen, obtaining explicit authorization, and resuming the existing Claude or Codex session. Once resumed, the task eventually reports a real terminal state (`done`/`failed`).

## User-clarification checkpoints

Different from an authorization checkpoint on every axis that matters: it isn't a mutation gate, and the main agent never guesses the answer. The generated contract tells every dispatched task to use `awaiting-user-input` when a substantive question about the *work itself* needs user judgment. A herdr-pane task asks and waits in its own pane so the user answers directly. A headless Codex task exits after persisting the checkpoint; after the user answers, the main agent relays that answer through `codex exec resume`. Headless Claude retains fail-and-redispatch behavior. Task prose supplies the context needed to avoid preventable questions; it does not restate this generic checkpoint.

**Escalation order for a stuck task.** Not every difficulty is a judgment call for the user, and not every blocker is even a question. Four distinct cases, in order:
1. **Missing context the main agent already has, that doesn't block continued progress while waiting** (another task's status, which apps are in scope) — use `send-dispatch-message.py --to main --intent question`. Do not use either checkpoint below.
2. **Blocked pending an action only the main agent's own judgment or dispatch authority can take** (redispatching a failed dependency, arbitrating a conflict with a peer task) — not a question, an action — this is `awaiting-main-agent` (see "Main-agent-action checkpoints" below).
3. **Genuine technical difficulty** — stuck on how to solve or debug something, not missing context, not an action only the main agent can take, and not a values/architecture call — try a stronger second opinion first, if one is available to the task (e.g. this session's own `advisor` tool, when present), before escalating further. Don't assume a specific tool is available; if none is, go straight to step 4.
4. **A judgment call reserved for the user** (which of several valid approaches, how to interpret an ambiguous requirement) — or genuine technical difficulty a second opinion didn't resolve — this is `awaiting-user-input`, as described above.

A second opinion is consultative, never decisive on the user's behalf — it can help the task get unstuck on *how*, it cannot make a call that's inherently the user's to make. It also never substitutes for the informational-question branch (step 1), for `awaiting-main-agent` (step 2), or for the authorization flow below, which is unaffected by any of this.

On an `awaiting-user-input` notification, the main agent's job is narrow: tell the user which task is asking and which pane/tab to go answer it in (from the dispatch instruction's recorded `herdr_pane_id`/`herdr_tab_id`), then leave it alone — same as `awaiting-authorization`, `dispatching-work`'s plan loop does not treat this as done, failed, or ready-for-a-new-wave, and does not auto-detach it. Once the user has answered directly in the pane, the task continues on its own and eventually reports a real terminal state or another checkpoint — the main agent does not need to explicitly "resume" it the way it does for an authorization checkpoint, because the conversation already happened directly in the pane.

**Not every mid-task question needs the user.** When a task's question is something the main agent can answer directly from what it already knows (another task's status, which apps are in scope) — not a judgment call about the work — every provider calls the instruction-keyed message script. Delivery is not authorization.

**Interactive answering is preferred through `herdr-pane`.** A headless Claude process cannot pause and resume, so it retains the existing behavior: report `failed` with the question in `--note`, then redispatch after the user answers. A headless Codex task can instead persist `awaiting-user-input`, exit, and later continue the recorded thread through `codex exec resume`; in that mode the main agent relays the user's answer because there is no live pane. Use `herdr-pane` whenever available so the user can answer directly and no relay is needed.

## Main-agent-action checkpoints

For being blocked on an action only the main agent's own judgment or dispatch authority can take (redispatching a failed dependency, arbitrating a conflict with a peer task) — not a mutation gate, not a question. The generated contract supplies `awaiting-main-agent` and its status command; task prose does not restate it.

**Resolved only through `reply-to-worker.py`** — never a manual pane reply:
```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/reply-to-worker.py" \
  --worker-instruction-path <path> --reply "<text>"
```
Delivers the reply, confirms it landed, then records the resolution — one call. `status` stays `awaiting-main-agent` afterward (the worker's own next terminal write closes it out, same as `awaiting-user-input`); the script only adds `resolved_by_main_agent_at`/`main_agent_reply`.

If resolving takes more than a couple of tool calls, an optional `send-dispatch-message.py --to worker --intent inform` nudge lets the worker know it is being handled. `reply-to-worker.py` is still what resolves the checkpoint.

On this status event (also delivered live through herdr when recorded), the main agent resolves it directly — no "tell the user which pane" step, unlike `awaiting-user-input`.

The direct reply script requires `herdr-pane`, but supports both Claude and Codex. A headless Codex checkpoint is continued through the recorded thread id using `codex exec resume` as documented in `dispatch-mechanics.md`; a headless Claude task retains its existing fail-and-redispatch behavior.

## Reporting status (script given to every dispatched task)

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/report-task-status.py" \
  --instruction-path <path> --status done --note "..."
```
The generated contract tells every dispatched task to run this on completion or failure — it resolves to `status/<task-id>.json` the same as the older `--plan <plan-slug> --task <task-id>` form (both still work; `--instruction-path` is preferred since the agent already has that path and doesn't need to separately track its own plan slug/task_id). The script writes only that one status file — it must never touch `plan.json` or another task's status file.

This command is the provider-neutral reporting seam. It writes the durable state that Plan scheduling consumes, then calls shared transport for live notification. `watch-plan-status.py` observes each content revision and a fresh watcher re-emits current persisted states for recovery. Any task may call `report-progress.py --instruction-path <path> --note "<text>"` beforehand to log intermediate progress.

## Reading plan/task status (targeted, not full-file dumps)

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/read-plan-status.py" --plan <plan-slug> --task <task-id>
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/read-plan-status.py" --plan <plan-slug> --not-done
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/read-plan-status.py" --plan <plan-slug> --in-flight
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/read-plan-status.py" --plan <plan-slug> --ready
```
`--task` returns one task's status only. `--not-done` lists every task not yet terminal (`done`/`failed`/`cancelled`), including ones still `planned` (never dispatched) — this answers "what's left in this plan," not "what's currently occupying a slot." `--in-flight` is the narrower one for that: only tasks that are actually dispatched (not `planned`) and not yet terminal — use this, never `--not-done`, for any concurrency-cap/slot-counting math (e.g. `boss-say`'s batch dispatch), since `--not-done`'s count also includes the ready queue itself and overcounts in-flight by exactly its size. `--ready` computes and returns the current ready wave (every task whose `depends_on` are all `done` and whose own status is still `planned`) — use this instead of recomputing the graph by hand each time. None of these dump the full plan or the full status directory unless explicitly asked to (a `--full` flag, used rarely, e.g. when the user asks to see the whole plan).

## Computing and dispatching a wave

1. Run `read-plan-status.py --plan <slug> --ready` to get the current ready wave.
2. For every task in the wave: call `dispatch-task.py write --plan <slug> --task-id <task_id> ...` (per `dispatch-mechanics.md`), then dispatch — **all of them, not one at a time**. The script marks `plan.json`'s task `dispatched` as part of the same call, not a separate manual edit.
3. Every full-flow task in the wave gets its worktree created first — see the worktree-ownership section below — before the `claude-p`/`herdr-pane` dispatch itself.
4. The generated dispatch contract supplies the universal progress, communication, checkpoint, and terminal-report workflow. Each task brief leads with the **clear requested outcome** and gives **sufficient verified context** for a worker entering cold. A **possible implementation** stays a lead to inspect, not a boundary. The brief omits **generic lifecycle prose** and includes only verified, material task-specific constraints; exact cross-task artifact paths remain required context.

## Monitoring Plan status (provider-neutral scheduling signal)

Start one long-running watcher for the Plan:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/watch-plan-status.py" \
  --plan <plan-slug>
```

Run it through the harness's `Monitor`/background mechanism and name the Plan in
the description. It emits one JSON line for every valid status-file *content
revision*, not merely the first appearance of a filename. Therefore
`awaiting-main-agent` → `done`, `awaiting-authorization` → `done`, and an
explicit `cancelled` overwrite are all observable transitions.

A newly started watcher intentionally emits every currently persisted task
status once. This is recovery behavior: after compaction or a restarted main
agent, current Plan state becomes visible without depending on an earlier
provider mailbox message. Malformed/partially-written JSON is skipped and
retried on the next scan.

On every `done`/`failed` event, recompute `read-plan-status.py --ready` and
dispatch newly unblocked tasks. `awaiting-authorization`,
`awaiting-user-input`, and `awaiting-main-agent` remain non-terminal and never
free a slot; handle them through their authority branches above. The status
command's shared-transport call is the primary live notice. Plan correctness
still depends on the watcher plus persisted status.

## Auto-detach on terminal state

**A task_id getting a same-task continuation isn't finished yet — don't call `wrap-up-task.py` for it ("Same-task continuation" below).** That script archives the instruction-keyed contract and transport state and syncs `plan.json`; running it early would remove the same identity phase 2 still needs. Recognizing a continuation is the main agent's own call from plan/task context.

Auto-detach triggers on `done`/`failed`/`cancelled` — **never** on `awaiting-authorization`, `awaiting-user-input`, or `awaiting-main-agent`, none of which is terminal — all three need the session to stay alive: one to be resumed once authorized, one to be answered directly by the user, one to be resolved directly by the main agent via `reply-to-worker.py`.

When the status watcher emits `done`/`failed`, or the main agent has just written `cancelled` itself (Cancel may also emit through the watcher, but the authoring main agent already knows synchronously):
1. If it was a full-flow, worktree-backed task, close per the "Worktree ownership" removal steps above (`herdr tab close` + `git worktree remove` — never `herdr workspace close`). Otherwise, if it was `herdr-pane` mode without a worktree, close its pane per `dispatch-mechanics.md`'s wrap-up rules (only close the tab too if it was the last pane in it). If the instruction included a shared-resource lock (above) and the task ended `failed`/`cancelled` before its own release step ran, release it now (`uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" release --resource <id> --holder <app>--<slug>`) — a lock left behind by a task that never got to clean up itself blocks every other main agent on that resource until its `ttl_seconds` expires otherwise.
2. Call `wrap-up-task.py --app <app> --slug <slug> --plan <slug> --task-id <task_id>` — it archives the instruction and syncs `plan.json`'s `tasks[].status` to the terminal status it reads from the status file, in one call. Do not `mv`/`Edit` these by hand.
3. Do **not** touch `plan.json.status` here — that only becomes `done` once every task in the plan is terminal (check across all tasks, not per-event).

**Once every task is terminal and `plan.json.status` is set to `done`, stop the status watcher** (`TaskStop`/the harness equivalent on its background task) — it does not self-terminate. This is the last step of marking a Plan done.

## Same-task continuation

**Checked before "Auto-detach on terminal state" above ever runs, not after** — once `wrap-up-task.py` has archived the instruction and synced `plan.json`, there's nothing left to reuse. Only when the next work is a later phase of the *same* logical task_id (never a different, independent task — those always get a fresh agent regardless of whether a finished session is sitting idle). This is the main agent's own judgment call, made straight from the plan/task context it already has — it doesn't need to check with the user before compacting and continuing.

For a Claude herdr pane, compact and continue through the instruction-keyed script:
```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <path> --to worker --intent control \
  --message "/compact <optional focus text>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <path> --to worker --intent redirect \
  --message "<phase 2 task text and exact reporting command>"
```
Two calls preserve queue order. Codex uses only the phase-2 message. Headless Codex uses its recorded thread id per `dispatch-mechanics.md`.

**Phase 2's completion needs its own report, stated explicitly in the phase-2 text.** This isn't a fresh dispatch instruction, so the continuation prompt must restate `report-task-status.py --instruction-path <path>`. The command writes the later status revision and prompts the recorded main-agent pane; the content-revision watcher emits the overwrite for recovery.

## Agent naming

Derive both the herdr agent name and any tab label from `plan_id`/`task_id`, e.g. `<plan-slug short>-<task-id>`. Do not use a generic or app-only name once a plan is involved — the point is that herdr's own `agent list`/pane listings reveal the plan/task without cross-referencing files. Validate the derived name before use — format and live-uniqueness both — per `dispatch-mechanics.md`'s step 4 (`check-agent-name.py`).

## Worktree ownership (every managed app, uniformly)

**Do not use `herdr worktree create`.** It always opens a brand-new herdr workspace with no way to target an existing one instead (`--workspace` only names the *source* repo, not a destination; confirmed against `herdr api schema --json` and the herdr project's own acknowledgement of this gap in [GitHub Discussion #553](https://github.com/herdrdev/herdr/discussions/553)) — one worktree per plan would mean one stray workspace per task, which is exactly what this mechanism must not do. Create the worktree with plain git instead, then, if the task is herdr-pane mode, add it to the *existing* workspace as a tab:

```bash
git -C "<app_dir>" worktree add "<app_dir>-<slug>" -b "<branch>" "<base_branch>"
```
Applies regardless of whether the target app has its own git-workflow skill.

**Mandatory verification after every call** (confirmed necessary live, not a hypothetical — and confirmed to reproduce identically whether the worktree was created via `git worktree add` or the old `herdr worktree create`, so this step stays mandatory regardless of creation method):
```bash
cd "<app_dir>-<slug>" && git rev-parse --show-toplevel
```
If this does not equal `<app_dir>-<slug>` exactly, the worktree is broken (confirmed root cause: repos with `extensions.worktreeConfig = true` don't get a per-worktree `core.worktree` override written automatically). Repair:
```bash
cat > "<git-common-dir>/worktrees/<worktree-name>/config.worktree" <<EOF
[core]
	worktree = <app_dir>-<slug>
	bare = false
EOF
```
(`<git-common-dir>` is `git -C <app_dir> rev-parse --git-common-dir`; `<worktree-name>` is usually the branch/slug name — confirm via `ls <git-common-dir>/worktrees/`.) Re-run the verification command after writing the repair file. Do not dispatch into a worktree that still fails verification after one repair attempt — stop and report it. `git worktree repair` does **not** fix this class of problem — do not reach for it.

**Copy the target app's declared local-only files, once verification passes.** `git worktree add` only checks out tracked files — anything gitignored (`.env`, `.env.local`, `certs/`, per-tenant local config) is missing from a fresh worktree, and an agent either fails to run or has to discover and copy it itself mid-task, both a worse experience than getting it upfront. Read the resolved app's `localFiles` entry in `.claude/straw-boss/apps.json` (see `skills/init/references/apps-config-schema.md`) — copy only the files listed there, each `path` relative to the app's `dir`. Blind-copy only (`cp -r`, never `Read`/`cat`) so file contents never enter the main agent's own context. If an entry has `sensitive: true`, ask the user once before copying it, even though it's already listed in the config — a config entry pre-authorizes *that the file exists and is expected*, not that copying live credentials needs no confirmation. An app with no `localFiles` entries has nothing to copy — that's the common case, not a gap.

Skip silently (no error) when a listed source file doesn't exist in the main checkout — not every dev environment has every optional local file set up.

**Joining the plan's shared workspace (herdr-pane mode only).** All worktree-backed tabs for the same plan land in one workspace — never a fresh one per task. That workspace is, by construction, the main agent's own: when the main agent is itself running inside a herdr pane, `$HERDR_WORKSPACE_ID` names it (confirmed set alongside `HERDR_ENV`).
```bash
herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "<app_dir>-<slug>" --label "<slug>"
```
Confirmed live: `tab create` (unlike `worktree create`) genuinely accepts an explicit `--workspace` target and lands the new tab there. There is no per-task decision to make about which workspace to target or whether it's "shared with the main agent" — it always is, because this mechanism never creates a new one. Without `--no-focus`, the new tab takes focus — on a plan's wave dispatch (every ready task at once), expect focus to jump once per task in the wave. If the main agent is not itself running inside a herdr pane (no `$HERDR_WORKSPACE_ID`), there is no workspace to join — the task falls back to `claude-p` mode per `dispatch-mechanics.md`, where workspace/tab concepts don't apply.

The launcher starts a full-flow task in the verified worktree, so the task brief does not narrate worktree creation or warn the worker not to repeat it. Everything after worktree creation (commit, MR/release mechanics) still follows the target app's own conventions where one exists — only the worktree-creation step moved.

**Removal, symmetrically, never touches the shared workspace itself:**
```bash
herdr tab close <tab_id>
git -C "<app_dir>" worktree remove "<app_dir>-<slug>"
```
Not `herdr worktree remove` (that primitive assumes the old one-workspace-per-worktree model and errors `not_linked_worktree` once a workspace holds more than one worktree's tab) and not `herdr workspace close` (the workspace is the main agent's own — possibly still in active use by the human user or the main agent itself — and this mechanism never owns its lifecycle, only the tabs it added to it).

## Rebase before push (parallel sibling tasks against the same base)

A full-flow task's worktree is created once, at wave-dispatch time, from whatever the base branch's tip was then (`references/plan-mechanics.md`'s "Worktree ownership" `git worktree add ... "<base_branch>"` above). If other tasks in the same plan target the same base branch and merge into it while this task is still working — the common case for any wave with more than one full-flow task — this task's worktree silently falls behind. Pushing from a stale base risks a merge (or, worse, a fast-forward) that reintroduces already-merged sibling files as deletions.

**Confirmed live, twice in one plan round** (two different full-flow tasks, each caught only because the main agent independently diffed against the live remote branch before authorizing the push): `git diff --stat origin/<base_branch>..HEAD` showed a sibling task's already-merged files listed as deletions — the tell that this worktree's base predates that merge, not that this task's own change actually deletes anything.

Every full-flow dispatch instruction in a plan/batch MUST tell the agent: immediately before pushing or opening the MR (not only at worktree creation), run
```bash
git fetch origin && git merge --ff-only origin/<base_branch>
```
(or an equivalent rebase) and resolve to a clean, non-diverged state first. This is a standing instruction, not something the main agent should have to notice and prompt for after the fact — the round that first hit this gap didn't have the reminder in its dispatch instructions and needed two separate manual interventions; the fix is to always include it, not to catch it via review.

## Failure handling

On a watcher event reporting `status: failed` for a task, read that task's status file's `note` field, and if it isn't conclusive, invoke `peeking-work` on that task to judge whether the failure looks like a permission denial (Claude Code declining an action rather than the task failing on its own merits) — don't read the transcript inline here. If it does, tell the user plainly and ask whether to redispatch that specific task with a permission bypass (`claude --dangerously-skip-permissions`/`--allow-dangerously-skip-permissions`, per `claude --help`) — **every time, never applied automatically**. A non-permission failure is reported to the user as a failure; redispatching it is the user's call, same as any other failure, not something this mechanism decides on its own.

## Shared-resource coordination (ports, DB migrations — cross-main-agent, not just cross-task)

Worktree isolation covers files, not a fixed network port a dev server binds to or a database multiple main agents' tasks might verify migrations against — both live outside any one checkout, and outside any one main agent's own visibility (a main agent has no idea what another, independently running main agent has dispatched). Do not add a generic collision warning to every task. If the task is actually expected to run a local dev server or touch a shared database for migration verification, follow `references/shared-resource-coordination.md` and include the exact `claim-resource.py claim-port` or `wait` command as material task context. Set `--requester-instruction-path` to this dispatch's instruction path; no raw main-agent endpoint is stored in the lock.
