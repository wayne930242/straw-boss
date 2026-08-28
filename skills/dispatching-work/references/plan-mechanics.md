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
or, for a team-mode task that reached a merge or other-branch-push checkpoint (see "Authorization checkpoints" below):
```json
{"status": "awaiting-authorization", "note": "what it's ready to do -- e.g. \"ready to merge branch fix-foo into main\"", "timestamp": "..."}
```
or, for a task that hit a substantive work-content question, not a git mutation (see "User-clarification checkpoints" below):
```json
{"status": "awaiting-user-input", "note": "the question it's asking -- e.g. \"which of two existing approaches should this follow?\"", "timestamp": "..."}
```
or, for a dispatch cancelled under `docs/roles.md`'s explicit user/objective-invalidity boundary (mechanics in `cross-session-coordination.md`):
```json
{"status": "cancelled", "note": "why the dispatch itself was wrong, not what the agent did", "timestamp": "..."}
```
`cancelled` is written by the main agent itself, never the dispatched task -- the only status value in this file with that property, since every other value is the dispatched task reporting on itself.

`awaiting-authorization`, `awaiting-user-input`, and `awaiting-main-agent` are all not terminal — the task's own `plan.json` entry stays `dispatched`, none joins or leaves the ready wave. All three exist so `watch-plan-status.py` can emit the checkpoint the same way it emits `done`/`failed`, instead of a task sitting silently idle with no signal that it's actually waiting on someone.

## Authorization checkpoints (team-mode only)

An agent must stop and report readiness rather than execute a merge, or a push landing outside its own feature branch. In an interactive pane the user answers directly; for a headless task the main agent relays the user's answer. Commit and a push of the task's own feature branch need no authorization. The generated contract supplies the checkpoint; task prose states only a material task-specific boundary absent from target-project instructions.

The plan loop leaves `awaiting-authorization` attached and non-terminal. Its caller points the user to an interactive pane or relays the user's answer to a headless continuation. The task later reports a terminal state.

## User-clarification checkpoints

Different from an authorization checkpoint on every axis that matters: it isn't a mutation gate, and the main agent never guesses the answer. The generated contract tells every dispatched task to use `awaiting-user-input` when a substantive question about the *work itself* needs user judgment. A herdr-pane task asks and waits in its own pane so the user answers directly. A headless Codex task exits after persisting the checkpoint; after the user answers, the main agent relays that answer through `codex exec resume`. Headless Claude retains fail-and-redispatch behavior. Task prose supplies the context needed to avoid preventable questions; it does not restate this generic checkpoint.

**Escalation order.** Discuss work details and judgment with the user directly; a headless task persists `awaiting-user-input` for relay. Ask the main agent only for integrated instructions, cross-task context, or a coordinator-owned action, using a non-blocking question or `awaiting-main-agent`. Ask peers only for factual progress or conclusions.

On an `awaiting-user-input` notification, the main agent's job is narrow: tell the user which task is asking and which worker pane to answer (from `herdr_pane_id`), then leave it alone. The plan loop does not treat this as done, failed, or ready for another wave. Once the user answers in that pane, the task continues and later reports another state.

**Not every mid-task question needs the user.** When a task's question is something the main agent can answer directly from what it already knows (another task's status, which apps are in scope) — not a judgment call about the work — every provider calls the instruction-keyed message script. Delivery is not authorization.

**Interactive answering is preferred through `herdr-pane`.** A headless Claude process cannot pause and resume, so it retains the existing behavior: report `failed` with the question in `--note`, then redispatch after the user answers. A headless Codex task can instead persist `awaiting-user-input`, exit, and later continue the recorded thread through `codex exec resume`; in that mode the main agent relays the user's answer because there is no live pane. Use `herdr-pane` whenever available so the user can answer directly and no relay is needed.

## Main-agent-action checkpoints

Use `awaiting-main-agent` only for integrated context or a coordinator-owned
action result. It is not a work-content decision or mutation gate; those stay
with the user and dispatched agent.

**Resolved only through `reply-to-worker.py`** — never a manual pane reply:
```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/reply-to-worker.py" \
  --worker-instruction-path <path> --reply "<text>"
```
Delivers the reply, confirms it landed, then records the resolution — one call. `status` stays `awaiting-main-agent` afterward (the worker's own next terminal write closes it out, same as `awaiting-user-input`); the script only adds `resolved_by_main_agent_at`/`main_agent_reply`.

If resolving takes more than a couple of tool calls, an optional `send-dispatch-message.py --to worker --intent inform` nudge lets the worker know it is being handled. `reply-to-worker.py` is still what resolves the checkpoint.

On this status event (also delivered live through Herdr when recorded), the main
agent supplies the owned fact or action result. Route work-content judgment to
the user instead.

The direct reply script requires `herdr-pane`, but supports both Claude and Codex. A headless Codex checkpoint is continued through the recorded thread id using `codex exec resume` as documented in `dispatch-mechanics.md`; a headless Claude task retains its existing fail-and-redispatch behavior.

## Reporting status (script given to every dispatched task)

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/report-task-status.py" \
  --instruction-path <path> --status done --note "..."
```
The generated contract tells every dispatched task to run this on completion or failure — it resolves to `status/<task-id>.json` the same as the older `--plan <plan-slug> --task <task-id>` form (both still work; `--instruction-path` is preferred since the agent already has that path and doesn't need to separately track its own plan slug/task_id). The script writes only that one status file — it must never touch `plan.json` or another task's status file.

This command is the provider-neutral reporting seam. For `done` and `failed`, it
writes durable state first and then notifies the recorded main-agent Herdr
endpoint. `watch-plan-status.py` observes each revision and re-emits persisted
state for recovery. Any task may report intermediate progress beforehand.

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
3. Every team-mode task in the wave gets its worktree created first — see the worktree-ownership section below — before the `claude-p`/`herdr-pane` dispatch itself.
4. The generated dispatch contract supplies the universal progress, communication, checkpoint, and terminal-report workflow. Author every brief within `dispatching-work` Task 3's brief boundary: carry the user requirement, requested outcome, necessary hints/constraints, and already-known coordination facts while leaving target-app context discovery to the worker. The worker and user choose the **specification, design, implementation, and the verification method inside the reality anchor the brief names**. Parallel tasks need non-overlapping requirement scopes; otherwise add a dependency instead of sharing a wave. Generic lifecycle prose stays out.

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

**A task_id getting a same-task continuation isn't finished yet — don't call `wrap-up-task.py` for it ("Same-task continuation" below).** That script archives the instruction-keyed contract and transport state and syncs `plan.json`; running it early would remove the same identity a later phase in the user-confirmed plan still needs.

Auto-detach triggers on `done`/`failed`/`cancelled` — **never** on `awaiting-authorization`, `awaiting-user-input`, or `awaiting-main-agent`, none of which is terminal — all three need the session to stay alive: one to be resumed once authorized, one to be answered directly by the user, one to be resolved directly by the main agent via `reply-to-worker.py`.

When the status watcher emits `done`/`failed`, or the main agent has just written `cancelled` itself (Cancel may also emit through the watcher, but the authoring main agent already knows synchronously):
1. Close the worker pane only; its tab is shared with the coordinator. For a team-mode task, then remove the worktree with plain git. Release any shared-resource lock still held on this instruction, whatever the terminal status — `shared-resource-coordination.md`'s "Releasing every lock on a wrapped-up instruction".
2. For a landed programming change whose review is not recorded yet, confirm the completion reference and apply `choosing-graph`'s single review checkpoint before Step 3 archives it.
3. Call `wrap-up-task.py --app <app> --slug <slug> --plan <slug> --task-id <task_id>` — it archives the instruction and syncs `plan.json`'s `tasks[].status` to the terminal status it reads from the status file, in one call. Do not `mv`/`Edit` these by hand.
4. Do **not** touch `plan.json.status` here — that only becomes `done` once every task in the plan is terminal (check across all tasks, not per-event).

**Once every task is terminal and `plan.json.status` is set to `done`, stop the status watcher** (`TaskStop`/the harness equivalent on its background task) — it does not self-terminate. This is the last step of marking a Plan done.

## Same-task continuation

**Checked before "Auto-detach on terminal state" above ever runs, not after** — once `wrap-up-task.py` has archived the instruction and synced `plan.json`, there's nothing left to reuse. Continue only when the already user-confirmed plan defines a later phase of the same logical task_id. A different task gets a fresh agent, and the main agent does not invent a new phase.

For a Claude herdr pane, compact and continue through the instruction-keyed script:
```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <path> --to worker --intent control \
  --message "/compact <optional focus text>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <path> --to worker --intent redirect \
  --message "Continue phase 2 from the referenced instruction." \
  --ref "<phase-2 instruction artifact>"
```
Two calls preserve queue order. Codex uses only the phase-2 message. Headless Codex uses its recorded thread id per `dispatch-mechanics.md`.

**Phase 2's artifact contains the full instruction and its own report command.**
This isn't a fresh dispatch instruction, so the referenced content must include
`report-task-status.py --instruction-path <path>`. The command writes the later
status revision; the watcher emits the overwrite for recovery.

## Agent naming

No plan-specific rule: each task dispatches through the same
`launch-dispatched-agent.py` as a standalone task and gets the same
automatically derived handle (`dispatch-mechanics.md`'s "Interactive herdr
launch"). Pass `--role` on `dispatch-task.py write` with the task's short
workroom label when `plan.json`'s task `description` (or already-known
coordination context) names one — e.g. a `database` task and a `frontend` task
sharing `app: "api"` still name apart as `database-worker`/`frontend-worker`
rather than collapsing to `api-worker`/`api-worker-2`. Only fall back to a bare
`<app>-worker` when the wave genuinely gives no per-task role signal.

## Worktree ownership (every managed app, uniformly)

**Do not use `herdr worktree create`.** It opens a separate workspace and breaks
the shared-tab invariant. Create the worktree with plain git; the launcher later
uses that path as the cwd of a pane split from the coordinator:

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

**Same-tab worker panes (herdr-pane mode only).** Record the verified worktree as
the instruction's `repo_root`. `launch-dispatched-agent.py` resolves the recorded
main pane and runs `herdr pane split <main-pane> --direction right --cwd
<repo_root> --no-focus`. It rejects a split whose returned `tab_id` differs from
the main pane. Every ready-wave worker therefore appears beside the coordinator
inside one tab; no task owns a tab lifecycle.

The launcher starts a team-mode task in the verified worktree, so the task brief does not narrate worktree creation or warn the worker not to repeat it. Everything after worktree creation (commit, MR/release mechanics) still follows the target app's own conventions where one exists — only the worktree-creation step moved.

**Removal closes only the worker pane:**
```bash
herdr pane close <pane_id>
git -C "<app_dir>" worktree remove "<app_dir>-<slug>"
```
The coordinator pane and shared tab remain open. `herdr worktree remove` and
workspace-level removal are outside this lifecycle; plain git owns the worktree.

## Rebase before push (parallel sibling tasks against the same base)

A team-mode task's worktree is created once, at wave-dispatch time, from whatever the base branch's tip was then (`references/plan-mechanics.md`'s "Worktree ownership" `git worktree add ... "<base_branch>"` above). If other tasks in the same plan target the same base branch and merge into it while this task is still working — the common case for any wave with more than one team-mode task — this task's worktree silently falls behind. Pushing from a stale base risks a merge (or, worse, a fast-forward) that reintroduces already-merged sibling files as deletions.

**Confirmed live, twice in one plan round** (two different team-mode tasks, each caught only because the main agent independently diffed against the live remote branch before authorizing the push): `git diff --stat origin/<base_branch>..HEAD` showed a sibling task's already-merged files listed as deletions — the tell that this worktree's base predates that merge, not that this task's own change actually deletes anything.

When parallel tasks target the same moving base or the remote base advanced
since worktree creation, the dispatch instruction tells the worker to refresh
immediately before pushing or opening the MR:
```bash
git fetch origin && git merge --ff-only origin/<base_branch>
```
(or use the app's equivalent rebase workflow) and resolve to a clean,
non-diverged state first. The confirmed incident above grounds this instruction
for moving-base concurrency; otherwise the app's established git workflow owns
the pre-push sequence.

## Failure handling

On a watcher event reporting `status: failed` for a task, read that task's status file's `note` field, and if it isn't conclusive, invoke `peeking-work` on that task to judge whether the failure looks like a permission denial (Claude Code declining an action rather than the task failing on its own merits) — don't read the transcript inline here. If it does, tell the user plainly and ask whether to redispatch that specific task with a permission bypass (`claude --dangerously-skip-permissions`/`--allow-dangerously-skip-permissions`, per `claude --help`) — **every time, never applied automatically**. A non-permission failure is reported to the user as a failure; redispatching it is the user's call, same as any other failure, not something this mechanism decides on its own.

## Shared-resource coordination (ports, DB migrations — cross-main-agent, not just cross-task)

Worktree isolation covers files. When user input, a dependency report, or
verified coordination state identifies a port or database shared by concurrent
tasks, carry that constraint into the brief and point the worker to
`references/shared-resource-coordination.md`. The worker resolves the app-local
resource identity and exact command immediately before use, with this dispatch's
instruction path as requester identity.
