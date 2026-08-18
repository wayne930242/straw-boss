# Plan mechanics

Exact file formats, scripts, and command sequences for plan-aware dispatch. Extends `dispatch-mechanics.md` (single-instruction dispatch is unchanged and still the mechanism each plan task ultimately uses) — read that file too, this one only covers what's new for plans.

## Plan file

`<home>/.straw-boss/plans/<plan-slug>/plan.json`. Written once by `work-on` after the decomposition is confirmed with the user via `grilling`; afterward only the boss updates per-task `status` fields — never a dispatched agent's own session.

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

`plan.status`: `planning` (being confirmed) → `in-progress` (at least one task dispatched) → `done` (every task terminal). Each `tasks[].status`: `planned` → `dispatched` → `done`/`failed`. A task's `depends_on` lists other `task_id`s in the same plan — empty means it's part of the first ready wave.

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
or, for a full-flow task that reached a commit/push/merge checkpoint (see "Authorization checkpoints" below):
```json
{"status": "awaiting-authorization", "note": "what it's ready to do -- e.g. \"ready to commit 3 files\"", "timestamp": "..."}
```
or, for a task that hit a substantive work-content question, not a git mutation (see "User-clarification checkpoints" below):
```json
{"status": "awaiting-user-input", "note": "the question it's asking -- e.g. \"which of two existing approaches should this follow?\"", "timestamp": "..."}
```
`awaiting-authorization` and `awaiting-user-input` are both not terminal — the task's own `plan.json` entry stays `dispatched`, neither joins or leaves the ready wave. Both exist so `Monitor` can detect the checkpoint the same way it detects `done`/`failed`, instead of a task sitting silently idle with no signal that it's actually waiting on someone.

## Authorization checkpoints (full flow only)

An agent must stop and report readiness rather than execute any commit/push/merge — the boss (in practice, `shipping-task`, not `dispatching-work` itself) obtains authorization and resumes it. Within a plan, that checkpoint is reported the same way completion is: the dispatch instruction for every full-flow task MUST tell the agent to call the status script with `--status awaiting-authorization` (not just stop silently) the moment it's ready to commit/push/merge, before it actually stops. This is what makes the checkpoint visible to `Monitor` — without it, a task waiting on authorization looks identical to a task still working, which is exactly the "silence is not success" failure `Monitor`'s coverage requirement exists to prevent.

`dispatching-work`'s own plan-dispatch loop (wave computation, parallel dispatch, auto-detach) treats `awaiting-authorization` as "leave this task alone, it isn't done or failed" — it does **not** attempt to authorize or resume it. That's `shipping-task`'s job (or whichever caller assembled the instruction and owns the authorization gate for it), watching the same `Monitor` notifications and, on an `awaiting-authorization` event for one of its tasks, doing what `shipping-task`'s own authorization step already does: state what's about to happen, get explicit authorization, resume the session to actually execute it. Once resumed, the task continues and eventually reports a real terminal state (`done`/`failed`).

## User-clarification checkpoints (`herdr-pane` only)

Different from an authorization checkpoint on every axis that matters: it isn't a mutation gate, and the boss doesn't act as an intermediary. A dispatched task's instruction MUST also tell it: if it hits a substantive question about the *work itself* — which of several valid approaches to take, how to interpret an ambiguous requirement, whether an existing OpenSpec change it found mid-task should be extended or left alone — that isn't a commit/push/merge decision, it calls the status script with `--status awaiting-user-input` and the question in `--note`, then asks the question directly in its own pane and waits there. The user can answer it directly in that pane — the boss does not need to relay the question or the answer, and should not try to guess the answer on the task's behalf.

On an `awaiting-user-input` notification, the boss's job is narrow: tell the user which task is asking and which pane/tab to go answer it in (from the dispatch instruction's recorded `herdr_pane_id`/`herdr_tab_id`), then leave it alone — same as `awaiting-authorization`, `dispatching-work`'s plan loop does not treat this as done, failed, or ready-for-a-new-wave, and does not auto-detach it. Once the user has answered directly in the pane, the task continues on its own and eventually reports a real terminal state or another checkpoint — the boss does not need to explicitly "resume" it the way it does for an authorization checkpoint, because the conversation already happened directly in the pane.

**Not every mid-task question needs the user.** When a task's question is something the boss can answer directly from what it already knows (another task's status, which apps are in scope) — not a judgment call about the work — it uses `SendMessage` to the boss instead of `awaiting-user-input`, and doesn't touch the status file at all for that exchange. See `references/cross-session-coordination.md` for addressing and the safety boundary (a peer's reply is never authorization for anything).

**This checkpoint only exists for `herdr-pane` tasks.** A `claude -p` process is not interactive — once it exits there is no live process left to answer a question to, so a `claude-p` task cannot genuinely pause and wait for a user reply. If a `claude-p` task hits a question it cannot resolve on its own, the closest it can do is report `failed` with the question stated in `--note`, ending the attempt — the user answers separately and the task gets redispatched with that answer folded into a new instruction. Because of this, `dispatching-work`'s mode selection (its own Task 1) requires `herdr-pane` — not just prefers it — whenever a task seems likely to need mid-task clarification (e.g. `work-on` found an existing OpenSpec change in the target app and the user's answer about it was ambiguous, or the task is genuinely open-ended) and herdr is available; only fall back to `claude-p` with an explicit caveat to the user when herdr genuinely isn't available for that dispatch.

## Reporting status (script given to every dispatched task)

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/report-task-status.py" \
  --plan <plan-slug> --task <task-id> --status done --note "..."
```
Every dispatch instruction for a plan task MUST tell the agent to run this on completion or failure — this is how the boss finds out, not by asking the agent directly. The script writes only `status/<task-id>.json` — it must never touch `plan.json` or another task's status file.

## Reading plan/task status (targeted, not full-file dumps)

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/read-plan-status.py" --plan <plan-slug> --task <task-id>
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/read-plan-status.py" --plan <plan-slug> --not-done
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/read-plan-status.py" --plan <plan-slug> --ready
```
`--task` returns one task's status only. `--not-done` lists tasks not yet `done`/`failed`. `--ready` computes and returns the current ready wave (every task whose `depends_on` are all `done` and whose own status is still `planned`) — use this instead of recomputing the graph by hand each time. None of these dump the full plan or the full status directory unless explicitly asked to (a `--full` flag, used rarely, e.g. when the user asks to see the whole plan).

## Computing and dispatching a wave

1. Run `read-plan-status.py --plan <slug> --ready` to get the current ready wave.
2. For every task in the wave: call `dispatch-task.py write --plan <slug> --task-id <task_id> ...` (per `dispatch-mechanics.md`), then dispatch — **all of them, not one at a time**. The script marks `plan.json`'s task `dispatched` as part of the same call, not a separate manual edit.
3. Every full-flow task in the wave gets its worktree created first — see the worktree-ownership section below — before the `claude-p`/`herdr-pane` dispatch itself.
4. Every dispatch instruction for a plan task explicitly states: (a) run the status-reporting script on completion/failure, (b) never touch any tracker ticket, (c) if worktree-backed, the shared-resource-coordination text (see below — a caveat at minimum, an actual `claim-port`/`wait` command if the task will run a dev server or touch a shared DB) and that the worktree already exists at the given path, (d) if another task in the plan depends on this one, the exact `artifacts/` path (see "Cross-task artifacts" above) to write its real output to — and if this task depends on another, the exact `artifacts/` path to read that prerequisite's output from, stated as required input, not optional context, (e) for `herdr-pane` tasks, that a substantive work-content question (not a git mutation) gets reported via `awaiting-user-input` and asked directly in its own pane, per "User-clarification checkpoints" above — never guessed at or silently deferred.

## Monitoring completion

Confirmed working, this exact shape (this environment's `Monitor`/`Bash` tools run under **zsh**, not bash — two zsh-specific pitfalls below are not hypothetical, they were hit live):

```bash
seen=""
while true; do
  for f in $(find "<home>/.straw-boss/plans/<plan-slug>/status" -maxdepth 1 -name "*.json" 2>/dev/null); do
    case " $seen " in
      *" $f "*) continue ;;
    esac
    seen="$seen $f"
    task_status=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['status'])" "$f")
    task_id=$(basename "$f" .json)
    echo "task=$task_id status=$task_status"
  done
  sleep 1
done
```

Two zsh-specific gotchas, both confirmed by hitting them:
- **Use `find ... -name "*.json"`, not a bare glob (`status/*.json`).** zsh's default `nomatch` option aborts the whole script with `no matches found` when the glob matches zero files (e.g. the status directory is briefly empty) — bash would just pass the literal pattern through, which the `[ -f ]`-style guard is written to tolerate; zsh doesn't get that far. `find` sidesteps this entirely regardless of shell.
- **Never name a variable `status`.** zsh reserves `status` as a read-only special variable (last command's exit code, like `$?`) — assigning to it errors with `read-only variable: status` and kills the script. Use `task_status` or similar.

Use the `Monitor` tool with a command like the above (a real polling loop, not a one-shot check) — `description` should name the plan. The loop must emit a line for **every** status a task can report — `done`, `failed`, `awaiting-authorization`, and `awaiting-user-input` — not just `done`; a filter that only matches `done` goes silent on a stuck/crashed task and on one quietly waiting on someone, all of which read identically to "still running" (confirmed live for `done`/`failed`: both produced their own line in the same notification — the polling loop above already emits every status value it finds, so `awaiting-authorization`/`awaiting-user-input` are covered the same way without further changes). On a `done`/`failed` notification, recompute the ready wave (step 1 above) and dispatch anything newly unblocked. On an `awaiting-authorization` notification, hand it to whichever caller owns that task's authorization gate (typically `shipping-task`) — do not treat it as done, failed, or ready-for-a-new-wave. On an `awaiting-user-input` notification, tell the user which pane to go answer it in and otherwise leave the task alone — same non-terminal treatment, but no relaying, no resuming; the user's own reply in that pane is what un-blocks it.

## Auto-detach on terminal state

Auto-detach triggers on `done`/`failed` only — **never** on `awaiting-authorization` or `awaiting-user-input`, neither of which is terminal — both need the session to stay alive, one to be resumed once authorized, the other to be answered directly by the user.

When a task's status file reports `done`/`failed` (observed via the Monitor notification):
1. If it was a full-flow, worktree-backed task, close per the "Worktree ownership" removal steps above (`herdr tab close` + `git worktree remove` — never `herdr workspace close`). Otherwise, if it was `herdr-pane` mode without a worktree, close its pane per `dispatch-mechanics.md`'s wrap-up rules (only close the tab too if it was the last pane in it). If the instruction included a shared-resource lock (above) and the task ended `failed` before its own release step ran, release it now (`uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" release --resource <id> --holder <app>--<slug>`) — a lock left behind by a task that never got to clean up itself blocks every other boss on that resource until its `ttl_seconds` expires otherwise.
2. Call `wrap-up-task.py --app <app> --slug <slug> --plan <slug> --task-id <task_id>` — it archives the instruction and syncs `plan.json`'s `tasks[].status` to the terminal status it reads from the status file, in one call. Do not `mv`/`Edit` these by hand.
3. Do **not** touch `plan.json.status` here — that only becomes `done` once every task in the plan is terminal (check across all tasks, not per-event).

**Once every task is terminal and `plan.json.status` is set to `done`, stop the `Monitor`** (`TaskStop` on its task id) — it does not self-terminate and will otherwise keep polling silently until its timeout. This isn't optional cleanup, it's the last step of marking a plan done, not a separate afterthought to remember later.

## Same-task continuation (`/compact` then phase 2)

Only when the next task is a later phase of the *same* logical task (never a different, independent task — those always get a fresh agent regardless of whether a finished session is sitting idle):
```bash
herdr agent prompt "<same-agent-name>" "/compact <optional focus text>" 
herdr agent prompt "<same-agent-name>" "<phase 2 task text>" --wait --timeout <ms>
```
Two separate calls. Do not wait for the compact call to settle before sending the second — Claude Code processes queued input in order.

## Agent naming

Derive both the herdr agent name and any tab label from `plan_id`/`task_id`, e.g. `<plan-slug short>-<task-id>` — must match `[a-z][a-z0-9_-]{0,31}` and be unique among live agents (check `herdr agent list` first if unsure). Do not use a generic or app-only name once a plan is involved — the point is that herdr's own `agent list`/pane listings reveal the plan/task without cross-referencing files.

## Worktree ownership (every managed app, uniformly)

**Do not use `herdr worktree create`.** It always opens a brand-new herdr workspace with no way to target an existing one instead (`--workspace` only names the *source* repo, not a destination; confirmed against `herdr api schema --json` and the herdr project's own acknowledgement of this gap in [GitHub Discussion #553](https://github.com/herdrdev/herdr/discussions/553)) — one worktree per plan would mean one stray workspace per task, which is exactly what this mechanism must not do. Create the worktree with plain git instead, then, if the task is herdr-pane mode, add it to the *existing* workspace as a tab:

```bash
git -C "<repo_root>/apps/<app>" worktree add "<repo_root>/apps/<app>-<slug>" -b "<branch>" "<base_branch>"
```
Applies regardless of whether the target app has its own git-workflow skill.

**Mandatory verification after every call** (confirmed necessary live, not a hypothetical — and confirmed to reproduce identically whether the worktree was created via `git worktree add` or the old `herdr worktree create`, so this step stays mandatory regardless of creation method):
```bash
cd "<repo_root>/apps/<app>-<slug>" && git rev-parse --show-toplevel
```
If this does not equal `<repo_root>/apps/<app>-<slug>` exactly, the worktree is broken (confirmed root cause: repos with `extensions.worktreeConfig = true` don't get a per-worktree `core.worktree` override written automatically). Repair:
```bash
cat > "<git-common-dir>/worktrees/<worktree-name>/config.worktree" <<EOF
[core]
	worktree = <repo_root>/apps/<app>-<slug>
	bare = false
EOF
```
(`<git-common-dir>` is `git -C <repo_root>/apps/<app> rev-parse --git-common-dir`; `<worktree-name>` is usually the branch/slug name — confirm via `ls <git-common-dir>/worktrees/`.) Re-run the verification command after writing the repair file. Do not dispatch into a worktree that still fails verification after one repair attempt — stop and report it. `git worktree repair` does **not** fix this class of problem — do not reach for it.

**Copy the target app's declared local-only files, once verification passes.** `git worktree add` only checks out tracked files — anything gitignored (`.env`, `.env.local`, `certs/`, per-tenant local config) is missing from a fresh worktree, and an agent either fails to run or has to discover and copy it itself mid-task, both a worse experience than getting it upfront. Read the resolved app's `localFiles` entry in `.claude/straw-boss/apps.json` (see `skills/init/references/apps-config-schema.md`) — copy only the files listed there, each `path` relative to the app's `dir`. Blind-copy only (`cp -r`, never `Read`/`cat`) so file contents never enter the boss's own context. If an entry has `sensitive: true`, ask the user once before copying it, even though it's already listed in the config — a config entry pre-authorizes *that the file exists and is expected*, not that copying live credentials needs no confirmation. An app with no `localFiles` entries has nothing to copy — that's the common case, not a gap.

Skip silently (no error) when a listed source file doesn't exist in the main checkout — not every dev environment has every optional local file set up.

**Joining the plan's shared workspace (herdr-pane mode only).** All worktree-backed tabs for the same plan land in one workspace — never a fresh one per task. That workspace is, by construction, the boss's own: when the boss is itself running inside a herdr pane, `$HERDR_WORKSPACE_ID` names it (confirmed set alongside `HERDR_ENV`).
```bash
herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "<repo_root>/apps/<app>-<slug>" --label "<slug>" --no-focus
```
Confirmed live: `tab create` (unlike `worktree create`) genuinely accepts an explicit `--workspace` target and lands the new tab there without disturbing the boss's own pane. There is no per-task decision to make about which workspace to target or whether it's "shared with the main agent" — it always is, because this mechanism never creates a new one. If the boss is not itself running inside a herdr pane (no `$HERDR_WORKSPACE_ID`), there is no workspace to join — the task falls back to `claude-p` mode per `dispatch-mechanics.md`, where workspace/tab concepts don't apply.

The dispatch instruction for a full-flow task states the worktree's path explicitly and that the agent must not create its own. Everything after worktree creation (commit, MR/release mechanics) still follows the target app's own conventions where one exists — only the worktree-creation step moved.

**Removal, symmetrically, never touches the shared workspace itself:**
```bash
herdr tab close <tab_id>
git -C "<repo_root>/apps/<app>" worktree remove "<repo_root>/apps/<app>-<slug>"
```
Not `herdr worktree remove` (that primitive assumes the old one-workspace-per-worktree model and errors `not_linked_worktree` once a workspace holds more than one worktree's tab) and not `herdr workspace close` (the workspace is the boss's own — possibly still in active use by the human user or the boss itself — and this mechanism never owns its lifecycle, only the tabs it added to it).

## Failure handling

On a `Monitor` notification reporting `status: failed` for a task, read that task's status file's `note` field, and if it isn't conclusive, invoke `peeking-work` on that task to judge whether the failure looks like a permission denial (Claude Code declining an action rather than the task failing on its own merits) — don't read the transcript inline here. If it does, tell the user plainly and ask whether to redispatch that specific task with a permission bypass (`claude --dangerously-skip-permissions`/`--allow-dangerously-skip-permissions`, per `claude --help`) — **every time, never applied automatically**. A non-permission failure is reported to the user as a failure; redispatching it is the user's call, same as any other failure, not something this mechanism decides on its own.

## Shared-resource coordination (ports, DB migrations — cross-boss, not just cross-task)

Worktree isolation covers files, not a fixed network port a dev server binds to or a database multiple bosses' tasks might verify migrations against — both live outside any one checkout, and outside any one boss's own visibility (a boss has no idea what another, independently running boss has dispatched). Every worktree-backed dispatch instruction includes, at minimum, this line verbatim (or equivalent): *"This worktree is isolated from other worktrees and the shared dev environment. If you run a local dev server to verify your changes, its default port may collide with another worktree's or the shared environment's port or hot-reload connection — check before assuming a bind failure means something else is wrong."*

If the task will actually run a local dev server or touch a shared (non-per-worktree) database for migration verification, go further — see `references/shared-resource-coordination.md` and put the exact `claim-resource.py claim-port` (flexible port) or `claim-resource.py wait` (fixed port or DB migration) command into the instruction, with `--requester-boss` set to the same boss-reachability value the instruction already carries for `notifying-boss` (`herdr-pane` gets its own pane id, both modes get the `SendMessage` peer name). No port is allocated or reassigned automatically beyond what that reference documents.
