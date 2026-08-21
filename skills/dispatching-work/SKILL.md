---
name: dispatching-work
description: Internal machinery that starts, tracks, lists, and closes out the agents this plugin runs — one per dispatched task, each rooted in its resolved app's own directory. Use after `boss-say`'s execution-tier call has landed on dispatch, for any of its specialist skills (`shipping-task`, `inspecting-app`, `investigating-app`, `troubleshooting-app`), once `work-on` has resolved the target app(s) (or a plan). Not this skill's to front directly — a user's status question ("what's running", "wrap this up") goes through `boss-say`, which calls the List/Wrap-up branches below. Not for one dispatch's live content (`peeking-work`).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework (inform/redirect/cancel) this skill implements the mechanics of — not redefined here.

**The unit this skill manages is the agent, not the app.** An app (`.claude/straw-boss/apps.json`, resolved upstream by `work-on`) is only *where* an agent is rooted — this skill starts the agent there, tracks it, and closes it out; it never itself decides which app a request belongs to. Every dispatched task is one agent, tracked as one instruction file under `~/.straw-boss/dispatch/` — the user's home directory, not the target project checkout (see `init`). This skill covers: **dispatch** a single agent (Tasks 1-5), **dispatch a plan** (Branch below, when `work-on` produced a multi-task dependency graph — one agent per task), **list**, and **wrap up**. Exact CLI/JSON syntax lives in `references/` — `dispatch-mechanics.md` (single-agent dispatch + permission-mode detection), `plan-mechanics.md` (plan/status schemas, worktree repair heredoc, zsh `Monitor` gotchas), `cross-session-coordination.md` (making the main agent addressable — herdr pane id primary, `SendMessage` fallback — plus mid-task interrupt syntax), `shared-resource-coordination.md` (a worktree isolates files, not a fixed port or a shared DB another *main agent's* task might collide on — one command per case: `claim-port` for a flexible port, `wait` for a fixed port or DB migration) — read the relevant one for the exact command before running it. Every requirement below is real, not a pointer to go read something else first. For a specific agent's actual live content or progress — not just its status — invoke `peeking-work` instead of reading a pane/transcript inline here.

`~/.straw-boss/capability.json` records an explicit `claude-p-only` opt-out from `init`, if the user ever gave one. Its absence is not a hard stop and is not evidence herdr is unavailable — see Task 1's no-`capability.json` handling; `claude-p` dispatch never needed it.

**Self-compact.** The main agent can compact its own context anytime, on its own judgment, regardless of dispatch mode or whether a plan is involved — `herdr agent prompt "$HERDR_PANE_ID" "/compact [focus]"` types the command into its own pane, the same mechanism `cross-session-coordination.md`'s `/rename` self-injection already uses, no separate tool or permission needed. It never needs to ask the user first. Reach for it once anything the next turn would need is already persisted somewhere durable (`plan.json`, an instruction file) rather than sitting only in this turn's own reasoning — full mechanics, including why this never interrupts work in flight, in `cross-session-coordination.md`'s "Self-compact".

## Task 1: Choose the dispatch mode and agent kind

Whether to dispatch into the app at all, versus handling something with a plain subagent, is `boss-say`'s call (its Task 1) — by the time this skill runs, that decision is already made. What's left here is transport, and it's an environment check, not a per-task judgment — never pick `claude-p` because a task "looks" self-contained or simple.

- **`capability.json` says `claude-p-only`** → `claude-p`, always. This is an explicit opt-out the user gave in `init`; honor it even if `HERDR_ENV` is `1` this session.
- **Otherwise, default to detecting herdr live rather than requiring a recorded capability** — `capability.json` saying `herdr-enabled`, or simply being absent (e.g. this dispatch didn't arrive via a path that ever ran `init`), are treated the same way: check this session's own `HERDR_ENV`.
  - **`HERDR_ENV` is `1`** → `herdr-pane`, always. `claude -p` is a black box with no way to pause for a live reply — there's no task shape that makes it the better choice once herdr exists.
  - **`HERDR_ENV` isn't `1`** → `claude-p` is the only option — there's no live herdr session for this main agent to join a tab/pane in. If the task looks likely to need mid-task clarification, say so — headless dispatch can't ask mid-task questions (it reports `failed` with the question stated instead of pausing), and running `init` would enable herdr-backed dispatch — but still proceed with `claude-p` if the user doesn't want to set that up now.

State the mode and why before doing anything else.

**Resolve the agent kind independently of mode** — see `references/dispatch-mechanics.md`'s "Resolving the agent kind": the target app's `apps.json` `agentKind` (defaults to `claude`), overridden for this one dispatch only when the task's nature matches a rule in root `CLAUDE.md`'s agent-routing policy (written by `init`'s Task 3, if the project has one) or an explicit request. State the resolved kind and why, same as mode. For a plan or batch task, the resolved kind must be `claude` regardless of the app's own default — see the Red Flag below.

**Before the first `herdr-pane` dispatch in this main-agent session** (not per-dispatch, not per-plan), ensure the main agent itself is addressable — see `references/cross-session-coordination.md` "Making the main agent addressable" for the exact mechanism. Skipping this is not a cosmetic gap: `SendMessage` does not fail loudly when an agent guesses the wrong target — it silently delivers to whatever session across the account happens to share a similar auto-derived title, which can be a stale, unrelated, offline session. Confirmed live: exactly this happened — an agent's coordination question was reported "sent" and was never seen again, no error anywhere.

**Verification:** mode stated with a reason; `herdr-pane` used whenever `capability.json` doesn't say `claude-p-only` and `HERDR_ENV` is `1` this session; `claude-p` used only because of an explicit opt-out or a genuinely absent live herdr session, never because the task looked simple; agent kind resolved and stated independently of mode; before the first `herdr-pane` dispatch this session, the main agent's own addressability was checked, not assumed.

## Task 2: Resolve batch membership

Several dispatches for one multi-app unit of work share a `batch` label (herdr-pane tab grouping only). A standalone dispatch has none.

## Task 3: Write the instruction, before dispatching

Call `dispatch-task.py write` (schema in `references/dispatch-mechanics.md`) — generates the session_id, writes the instruction (`status: pending`), and for a plan task marks `plan.json` `dispatched`, refusing before writing anything if that task isn't still `planned`. Pass the agent kind resolved in Task 1 as `--agent-kind` (and `--agent-model`/`--agent-effort` if that resolution chose an override) — the script itself refuses a non-`claude` kind for a plan/batch task and an unrecognized kind outright, so a mistake here surfaces immediately rather than silently. Never hand-write the JSON or generate a second UUID — the script is what keeps a rejected dispatch from leaving a stray file behind.

**Verification:** instruction exists with `pending` status before any `claude`/`herdr` command runs.

## Task 4: Dispatch

Follow `references/dispatch-mechanics.md` for the exact `claude`/`herdr` command sequence — don't improvise it from general knowledge.

**Mirror the main agent's own permission mode onto the agent.** Detect it from the main agent's own process args (`ps -p "$CLAUDE_PID" -ww -o args=`, exact detection in the reference) and map it through the agent kind's own permission surface (`references/dispatch-mechanics.md`'s "Mapping permission mode across agent kinds" — a per-kind flag combo, not the identical flag string, for anything other than `claude`). An agent must never end up more tightly gated than the main agent dispatching it — never hardcode a specific mode here, and never omit this "to be safe."

For `herdr-pane`, a `herdr agent prompt` success return is not proof of delivery — a first-run interruption can swallow the submission while the CLI still reports success. Confirm delivery (terminal-title check for claude, transcript check via `--source visible` for codex — both in the reference) before proceeding.

Once dispatch succeeds and delivery is confirmed, call `dispatch-task.py confirm` — flips to `in-progress`, records pane/tab ids for `herdr-pane`. For a kind that can't pre-assign a session id (e.g. `codex`), pass `--observed-session-id` with what the launched agent actually reported, per the reference's per-kind confirm step.

**Verification:** status is `in-progress`; permission mode was detected and mapped through the resolved agent kind's own permission surface, not hardcoded or skipped; pane/tab ids recorded for `herdr-pane`; session_id cross-checked against what herdr/the agent reports (or recorded from what it reported, for a kind that can't pre-assign one).

## Task 5: Report

Tell the user what was dispatched, in which mode, and how to find it (instruction path; pane/tab for `herdr-pane`).

## Branch: Dispatch a plan

Plans have their own file formats and a wave-scheduling step Tasks 1-5 don't — don't improvise this by analogy.

**Wave dispatch.** Compute the ready wave (`read-plan-status.py --ready`) and dispatch **every task in it at once** — never one at a time, never serialize an independent task through another task's session because it happens to be idle. Each task still goes through Tasks 1-5 individually (mode selection, instruction, dispatch, confirm), with `plan_id`/`task_id` added.

**Worktree ownership (full-flow tasks).** The main agent creates every worktree itself, for every managed app uniformly, regardless of the app's own tooling — plain `git worktree add`, never `herdr worktree create` (see `plan-mechanics.md`'s "Worktree ownership" for why). Verify `git rev-parse --show-toplevel` inside it resolves to the worktree's own path — repos with `extensions.worktreeConfig = true` silently don't, regardless of creation method — and repair with a `config.worktree` file if not (exact steps in `plan-mechanics.md`). Never dispatch into an unverified worktree. For `herdr-pane`, join it to the main agent's own existing workspace as a tab (`herdr tab create --workspace`) — a plan's worktrees never scatter across workspaces, and the shared workspace is never closed by this mechanism, only the tabs added to it.

**Agent naming.** Derive from `plan_id`/`task_id` for both herdr's own agent handle and the trailing `claude --name` flag — the same value serves herdr control (`agent get/prompt/read`) and `SendMessage`/`ListAgents` addressability, no separate naming decision.

**Cross-task artifacts.** When task B depends on task A and genuinely needs A's output, both dispatch instructions state the exact path under `~/.straw-boss/plans/<slug>/artifacts/` — A's says where to write it, B's says where to read it and that it's required input, not optional context. `plan.json`'s `description` field is prose, not a handoff mechanism.

**Six checkpoint/report types — never conflate them:**
| Status | For | Answered by | Terminal? |
|---|---|---|---|
| `awaiting-authorization` | merge, or a push landing outside the task's own feature branch (full flow only — light flow's commit needs no authorization) | User, relayed through the main agent (`shipping-task`) | No — main agent resumes after authorizing |
| `awaiting-user-input` | work-content question needing human judgment, or genuine technical difficulty a second opinion didn't resolve | User, directly in the agent's own pane — main agent only points at it | No — agent continues on its own once answered |
| `awaiting-main-agent` | blocked pending an action only the main agent's own judgment or dispatch authority can take (not a question) | Main agent itself, via `reply-to-worker.py` — no human needed | No — main agent resolves it, agent continues on its own once resumed |
| `SendMessage` to the main agent (question) | informational question the main agent can answer from what it already knows, that doesn't block continued progress while waiting | Main agent itself, no human needed (`references/cross-session-coordination.md`) | Not a status transition at all |
| `SendMessage` push (report) | reaching `done`/`failed`/a checkpoint — required, primary signal, per `notifying-main-agent`'s "Branch: Report your own status" | Main agent, guaranteed-delivery (unlike a herdr nudge, which is optional/additive only) | Not a status transition itself — accompanies whatever transition (`done`/`failed`/`awaiting-authorization`/`awaiting-main-agent`) is actually happening |
| `SendMessage` push (feature-branch push-FYI) | agent pushed its own feature branch and opened or updated an MR/PR — no authorization needed | Main agent, relayed to the user as an FYI (`shipping-task`'s Task 5) — not obtained, not resumed | Not a status transition at all — agent does not wait, continues immediately |

A task unsure which applies walks `plan-mechanics.md`'s "Escalation order for a stuck task" (full order there, not restated here). `awaiting-authorization` sits outside that order — it's the merge/other-branch-push readiness gate, not a response to being stuck; a push of the task's own feature branch needs no gate at all, reported as the FYI row above instead. All three `awaiting-*` checkpoints are `herdr-pane`, `agent_kind: claude` only; anything else reports `failed` with the situation in `--note`. The report-push row is unconditional — every dispatch sends it on reaching `done`/`failed`/a checkpoint, regardless of mode; the feature-branch push-FYI row is unconditional too, whenever that push happens.

**Same-task continuation — a task_id with a later phase coming isn't finished, don't wrap it up yet.** When a just-finished session has more of the *same* logical task_id coming (never a different, independent task), withhold `wrap-up-task.py` for it — that call atomically archives the instruction and marks the task done in `plan.json`, which would strand phase 2's own instruction lookup and mark the task complete prematurely. Reuse the session instead: two separate `herdr agent prompt` calls, `/compact [focus]` then the phase-2 text — the compact call is nothing more than typing `/compact` into that pane, the exact same mechanism as any other prompt, no separate tool or permission needed. Recognizing this and compacting is the main agent's own judgment call from the plan/task context already in hand; it never needs to ask the user first. The phase-2 text must restate the `SendMessage` reporting obligation itself — it's typed into an existing pane, not a fresh dispatch instruction, and the Monitor loop's filename dedup won't catch phase 2 rewriting the same status file (`plan-mechanics.md`'s "Same-task continuation").

**Monitor coverage (fallback).** Start a `Monitor` that emits on every status a task can report — `done`, `failed`, `cancelled`, `awaiting-authorization`, `awaiting-user-input`, `awaiting-main-agent` — not just completion (exact zsh-safe polling command in `plan-mechanics.md`, including the caveat that `cancelled` may not reliably produce its own notification — the main agent performing a cancel already knows and doesn't wait on one). This loop is the fallback for a task that's gone quiet without its `SendMessage` push arriving — see `plan-mechanics.md`'s "Monitoring completion" — not the primary way completion is learned about. `done`/`failed`/`cancelled` are terminal: on those, first check whether this task_id has a same-task continuation coming — only if it doesn't, auto-detach (close the pane/worktree tab per the rules above, call `wrap-up-task.py`, recompute + dispatch the next ready wave). `awaiting-authorization`/`awaiting-user-input`/`awaiting-main-agent` never trigger auto-detach — on `awaiting-main-agent`, resolve it directly with `reply-to-worker.py` (`plan-mechanics.md`'s "Main-agent-action checkpoints") rather than pointing the user at anything. On `failed`, if it looks like a permission denial, ask the user before ever redispatching with a bypass — never automatic. The plan is done only once every task is terminal, never on the first one finishing.

**Progress visibility.** A dispatched task may call `report-progress.py --instruction-path <path> --note "<text>"` at any point during its work — a separate, non-notifying, append-only log (`dispatch-mechanics.md`'s "Reporting scripts"). `peeking-work` reads this trail before joining a task's live pane, so checking on a task usually doesn't require interrupting it.

**Shared-resource coordination.** Every worktree-backed instruction states, verbatim or equivalent, that a local dev server in this worktree may collide with another worktree's or the shared environment's port/HMR — no port is auto-allocated. When the task will actually run a dev server or verify a migration against a shared (non-per-worktree) database, this is not just a caveat but a collision another *main agent's* task can also hit — worktrees don't isolate it. Follow `references/shared-resource-coordination.md` and put its exact `claim-port`/`wait` command into the instruction, `--requester-boss` set to the same value already given for `notifying-main-agent`; the agent claims and releases the resource itself, inline in its own task.

**Verification:** every ready-wave task dispatched together; a task with unresolved dependencies never dispatched early; worktree verified before dispatch; `wrap-up-task.py` withheld for any task_id with a same-task continuation coming, checked before it's ever called, not after; plan completion judged by all tasks terminal, never by the first.

## Branch: List outstanding instructions

Scan `~/.straw-boss/dispatch/` for `<app>--<slug>.json` instruction files only — excluding `archive/`, and excluding a standalone dispatch's own `<app>--<slug>.status.json`/`.progress.jsonl` siblings (per `dispatch-mechanics.md`'s "Reporting scripts"), which match a naive `*.json`/`*.jsonl` glob but are not instructions themselves — reading one as if it were would report a phantom, already-terminal entry that never actually gets wrapped up (`wrap-up-task.py` archives them alongside their real instruction, not standalone). Report grouped by status. Pure read.

## Branch: Wrap up an instruction

1. Confirm which instruction (ask if ambiguous).
2. If `herdr-pane` and the pane/tab is still open and no longer needed, close it first (`herdr pane close`/`herdr tab close` — tab only if it was the last pane in it). `claude-p` has nothing to close.
3. Call `wrap-up-task.py` — sets `wrapped-up`, archives the instruction file and, if present, its `.status.json`/`.progress.jsonl` siblings (per `dispatch-mechanics.md`'s "Reporting scripts") together, and for a plan task syncs `plan.json` to the terminal status read from that task's own status file. Refuses if a status record exists and isn't yet terminal (`done`/`failed`/`cancelled`) — for a plan task from its `status/<task_id>.json`, for a standalone dispatch from its own `.status.json` if one was ever written (no record at all is not itself a refusal — an older dispatch, or a `claude-p` one confirmed done by process exit, may legitimately have none). Never `mv`/`Edit` this by hand.

**Verification:** pane/tab confirmed closed before the file is archived, never assumed.

## Red Flags

- "No herdr session available, ask the user to open one anyway" — last resort only; default to `claude-p` first.
- "No `capability.json`, stop and tell the user to run `init` first" — no, and don't default to `claude-p` either; a missing file isn't an opt-out, check `HERDR_ENV` live and use `herdr-pane` if it's `1`.
- "No `capability.json`, so herdr isn't confirmed available, use `claude-p`" — no, only an explicit `claude-p-only` opts out; absence means check `HERDR_ENV` live instead of assuming unavailable.
- "Skip writing the instruction until dispatch succeeds" — no, write it `pending` first; a stray pending file on failure is signal, not noise.
- "Reconstruct the herdr command sequence from memory" — no, always the reference.
- "This agent's mode doesn't matter, use whatever's default" — no, mirror the main agent's actual mode every time.
- "Pane looks closed already, skip confirming" — no, check via `herdr pane get`/`agent get` first.
- "This standalone dispatch has no plan, so wrap it up whenever, no status to check" — no, `wrap-up-task.py` now refuses if its own `.status.json` (if one was written) reports a non-terminal status, same guard a plan task already has.
- "Two unrelated dispatches, share a batch to save a tab" — no, batch is one multi-app unit of work only.
- "3 ready tasks, dispatch one at a time to keep it simple" — no, all at once, always.
- "This idle finished session could take the next ready task" — no, a `--ready` task is always a different `task_id`; only that exact task_id's own next phase reuses the session, never something the wave computation surfaced.
- "This task_id just went `done`, auto-detach it right away, check for a same-task phase 2 afterward if one comes up" — no, the check comes first; `wrap-up-task.py` archives the instruction and marks the task done in `plan.json` in one call, and by then there's nothing left to reuse.
- "This task_id has its own phase 2 coming, but ask the user before compacting and continuing" — no, recognizing same-task continuation and sending `/compact` is the main agent's own call from context it already has; decide and send it, no sign-off needed.
- "Compacting a worker session needs a special tool or API beyond what dispatch already uses" — no, `/compact` sent via `herdr agent prompt` is the identical mechanism used for every other prompt into that pane; nothing else is required to use it.
- "First task in the plan finished, mark the plan done" — no, only once every task is terminal.
- "This task looks simple/self-contained, use `claude-p` even though herdr's available" — no, mode is an environment check, not a task judgment; `herdr-pane` is used whenever it's available, full stop.
- "The task's mid-flight question, relay it like an authorization checkpoint" — no, `awaiting-user-input` is answered directly in the pane; a question the main agent can itself answer goes through `SendMessage` instead, not a status transition.
- "A task is genuinely blocked until I act, but not a human judgment call, so let it send an informational question" — no, that's `awaiting-main-agent`, not the fire-and-forget channel — it needs to be tracked, not queued at the same priority as any other async question.
- "I figured out the answer to this worker's `awaiting-main-agent` checkpoint, that's resolved" — no, only `reply-to-worker.py` resolves it; a reply typed manually into the pane, or only reasoned about, leaves the checkpoint silently stale.
- "The task wrote its status file, that's how the main agent finds out it's done" — no, per "Six checkpoint/report types" above: the status write is bookkeeping, not the notification; the task's `SendMessage` push is what's required, every time.
- "Rely on the `Monitor` polling loop, it'll catch every status change" — no, it's the fallback now, not the primary signal; a `Monitor` that isn't running (a fresh or resumed main-agent session, a dropped task) catches nothing until something else triggers a re-check.
- "Skip the worktree verify-repair step, herdr worktree create usually works fine" — no, the `config.worktree` bug happens with *any* creation method on a repo with `extensions.worktreeConfig`; verify every time.
- "Dispatch the herdr-pane task first, worry about main-agent addressability if an agent actually needs it" — no, Task 1 requires this checked *before* the first herdr-pane dispatch this session; an agent that needs the channel and finds it unaddressed doesn't get an error, it gets silent misdelivery to an unrelated session.
- "This coordination question sounds like something the main agent could reasonably weigh in on, SendMessage it" — no, per `cross-session-coordination.md`: any trade-off or "which direction" call is `awaiting-user-input`, full stop, regardless of how qualified the main agent seems.
- "The worktree isolates this task, so a shared-DB migration check can't collide with another main agent's task" — no, per `shared-resource-coordination.md`: worktree isolation is file-level only; a shared database is outside any one checkout and needs the lock regardless of worktree.
- "Have the main agent pre-acquire the shared-resource lock before dispatching, so the agent starts already holding it" — no, the agent acquires it itself, right before it actually needs the resource; acquiring earlier holds it uselessly against other main agents during unrelated implementation work.
- "This app's configured `agentKind` is `codex`, dispatch its plan/batch task under it directly" — no, "Resolving the agent kind"'s standalone-only rule: force that task to `claude` instead and state that the app's own default was overridden and why; a non-`claude` agent can't run `notifying-main-agent`, isn't reachable by name, and has no built-in way to honor the plan's status-file protocol.
