---
name: dispatching-work
description: Internal machinery that starts, tracks, lists, and closes out the agents this plugin runs — one per dispatched task, each rooted in its resolved app's own directory. Use after `boss-say`'s execution-tier call has landed on dispatch, for any of its specialist skills (`shipping-task`, `inspecting-app`, `investigating-app`, `troubleshooting-app`), once `work-on` has resolved the target app(s) (or a plan). Not this skill's to front directly — a user's status question ("what's running", "wrap this up") goes through `boss-say`, which calls the List/Wrap-up branches below. Not for one dispatch's live content (`peeking-work`).
---

## Overview

See `docs/roles.md` for the **own the loop, not the work** boundary. This skill
implements dispatch mechanics; a launched Herdr agent and the user choose its
specification, design, implementation, and verification method.

**The unit this skill manages is the agent, not the app.** An app (`.claude/straw-boss/apps.json`, resolved upstream by `work-on`) is only *where* an agent is rooted — this skill starts the agent there, tracks it, and closes it out; it never itself decides which app a request belongs to. Every dispatched task is one agent, tracked as one instruction file under `~/.straw-boss/dispatch/` — the user's home directory, not the target project checkout (see `init`). This skill covers: **dispatch** a single agent (Tasks 1-5), **dispatch a plan** (Branch below, when `work-on` produced a multi-task dependency graph — one agent per task), **list**, and **wrap up**. Exact CLI/JSON syntax lives in `references/` — `dispatch-mechanics.md` (single-agent dispatch + permission-mode detection), `plan-mechanics.md` (plan/status schemas, worktree repair heredoc, and the provider-neutral status watcher), `cross-session-coordination.md` (making the main agent addressable — herdr pane id primary, with provider-specific fast channels — plus mid-task interrupt syntax), `shared-resource-coordination.md` (a worktree isolates files, not a fixed port or a shared DB another *main agent's* task might collide on — one command per case: `claim-port` for a flexible port, `wait` for a fixed port or DB migration) — read the relevant one for the exact command before running it. Every requirement below is real, not a pointer to go read something else first. For a specific agent's actual live content or progress — not just its status — invoke `peeking-work` instead of reading a pane/transcript inline here.

`~/.straw-boss/capability.json` records an explicit `claude-p-only` opt-out from `init`, if the user ever gave one. Its absence is not a hard stop and is not evidence herdr is unavailable — see Task 1's no-`capability.json` handling; `claude-p` dispatch never needed it.

**Self-compact.** The main agent can compact its own context anytime, on its own judgment, regardless of dispatch mode or whether a plan is involved — `herdr agent prompt "$HERDR_PANE_ID" "/compact [focus]"` types the command into its own pane, the same mechanism `cross-session-coordination.md`'s `/rename` self-injection already uses, no separate tool or permission needed. It never needs to ask the user first. Reach for it once anything the next turn would need is already persisted somewhere durable (`plan.json`, an instruction file) rather than sitting only in this turn's own reasoning — full mechanics, including why this never interrupts work in flight, in `cross-session-coordination.md`'s "Self-compact".

## Task 1: Choose the dispatch mode and work route

Whether to dispatch into the app at all, versus handling something with a plain subagent, is `boss-say`'s call (its Task 1) — by the time this skill runs, that decision is already made. What's left here is transport, and it's an environment check, not a per-task judgment — never pick `claude-p` because a task "looks" self-contained or simple.

- **`capability.json` says `claude-p-only`** → `claude-p`, always. This is an explicit opt-out the user gave in `init`; honor it even if `HERDR_ENV` is `1` this session.
- **Otherwise, default to detecting herdr live rather than requiring a recorded capability** — `capability.json` saying `herdr-enabled`, or simply being absent (e.g. this dispatch didn't arrive via a path that ever ran `init`), are treated the same way: check this session's own `HERDR_ENV`.
  - **`HERDR_ENV` is `1`** → `herdr-pane`, always. `claude -p` is a black box with no way to pause for a live reply — there's no task shape that makes it the better choice once herdr exists.
  - **`HERDR_ENV` isn't `1`** → `claude-p` is the only option — there's no live herdr session beside which to open a worker pane. If the task looks likely to need mid-task clarification, say so — headless dispatch can't ask mid-task questions (it reports `failed` with the question stated instead of pausing), and running `init` would enable herdr-backed dispatch — but still proceed with `claude-p` if the user doesn't want to set that up now.

State the mode and why before doing anything else.

**Resolve the complete worker setup independently of mode** — see `references/dispatch-mechanics.md`'s "Resolving the work route." An explicit one-off setup wins, then a matching work route in root `CLAUDE.md`, then the target app's `apps.json.agentKind`, then Claude with provider defaults. Resolve agent kind, provider profile, model, effort, and the Claude Code native advisor together. State the resolved setup and why. Codex has no native advisor; refuse that combination instead of substituting a coworker. The same resolution applies to standalone, batch, and Plan tasks; dependency tracking is provider-neutral.

**Resolve the main agent's own provider and reachability before writing the instruction.** Pass `--main-agent-kind` on every dispatch. For `herdr-pane`, read this session's live herdr record and pass `$HERDR_PANE_ID` as `--main-agent-pane-id`, plus the provider fingerprint: Claude uses its exact `agent_session.value` with `--main-agent-session-id`; Codex uses its exact `terminal_id` with `--main-agent-terminal-id`. The shared transport requires the pane and the provider-selected fingerprint before sending anything.

**Verification:** mode stated with a reason; `herdr-pane` used whenever `capability.json` doesn't say `claude-p-only` and `HERDR_ENV` is `1` this session; `claude-p` used only because of an explicit opt-out or a genuinely absent live herdr session, never because the task looked simple; the complete worker setup was resolved and stated independently of mode; before the first `herdr-pane` dispatch this session, the main agent's own addressability was checked, not assumed.

## Task 2: Resolve batch membership

Several dispatches may share a `batch` label for tracking. A batch may contain
independent items; it is a reporting/group label, not proof of one multi-app
unit or a dependency relationship. A standalone dispatch has none.

## Task 3: Write the instruction, before dispatching

Build a concise brief from the user requirement, requested outcome, necessary
hints, explicit constraints, dependencies, and verified coordination facts
already available to the main agent. Target-app implementation, precedent, and
local-context discovery stays with the worker in its own working directory and
harness. The coordinator resolves the routing and dispatch mechanics.

For investigation, audit, or diagnosis, ask for an explanatory account of the
current behavior, mechanism, cause, or impact with evidence references. A
bounded fact-gathering task may use a confirmed lower-tier work route; route
resolution still comes from Task 1.

Call `dispatch-task.py write` (schema in `references/dispatch-mechanics.md`) — generates Claude's session id and every provider's immutable contract, writes the instruction (`status: pending`), and for a plan task marks `plan.json` `dispatched`, refusing before writing anything if that task isn't still `planned`. Pass the worker kind, this session's provider, and the validated pane/provider-fingerprint pair from Task 1. Never hand-write the JSON, contract, or UUID.

**Verification:** every brief statement traces to the user request, a necessary
hint or constraint, or already-known coordination state; target-app discovery is
assigned to the worker; instruction and hashed contract exist with `pending`
status before any agent starts.

## Task 4: Dispatch

Follow `references/dispatch-mechanics.md`. For `herdr-pane`, start and submit the task only through `launch-dispatched-agent.py`; it injects the generated contract before the first model turn, verifies the task reached the transcript with at most one retry, and only then writes the launch receipt consumed by `dispatch-task.py confirm`.

**Mirror the main agent's own permission mode onto the agent.** Detect it from the main agent's own process args (`ps -p "$CLAUDE_PID" -ww -o args=`, exact detection in the reference) and map it through the agent kind's own permission surface (`references/dispatch-mechanics.md`'s "Mapping permission mode across agent kinds" — a per-kind flag combo, not the identical flag string, for anything other than `claude`). An agent must never end up more tightly gated than the main agent dispatching it — never hardcode a specific mode here, and never omit this "to be safe."

Once the launcher succeeds, call `dispatch-task.py confirm`. It refuses unless the launch receipt matches the instruction, contract digest, provider, pane, and provider-specific live fingerprint; then it flips to `in-progress` and records the receipt's pane, tab, and identity fields.

**Verification:** status is `in-progress`; permission mode was detected and mapped through the resolved agent kind's own permission surface, not hardcoded or skipped; pane/tab ids recorded for `herdr-pane`; session_id cross-checked against what herdr/the agent reports (or recorded from what it reported, for a kind that can't pre-assign one).

## Task 5: Report

Tell the user what was dispatched, in which mode, and how to find it (instruction path; pane/tab for `herdr-pane`).

## Branch: Dispatch a plan

Plans have their own file formats and a wave-scheduling step Tasks 1-5 don't — don't improvise this by analogy.

**Wave dispatch.** Compute the ready wave (`read-plan-status.py --ready`) and dispatch **every task in it at once** — never one at a time, never serialize an independent task through another task's session because it happens to be idle. Each task still goes through Tasks 1-5 individually (mode selection, instruction, dispatch, confirm), with `plan_id`/`task_id` added.

**Worktree ownership (full-flow tasks).** The main agent creates every worktree itself, for every managed app uniformly, regardless of the app's own tooling — plain `git worktree add`, never `herdr worktree create` (see `plan-mechanics.md`'s "Worktree ownership" for why). Verify `git rev-parse --show-toplevel` inside it resolves to the worktree's own path — repos with `extensions.worktreeConfig = true` silently don't, regardless of creation method — and repair with a `config.worktree` file if not (exact steps in `plan-mechanics.md`). Never dispatch into an unverified worktree. Record that verified path as `repo_root`; the launcher opens its worker pane beside the coordinator in the same tab.

**Agent naming.** Derive the herdr handle from `plan_id`/`task_id` for operator visibility. Communication scripts address the instruction, never this name.

**Cross-task artifacts.** When task B depends on task A and genuinely needs A's output, both dispatch instructions state the exact path under `~/.straw-boss/plans/<slug>/artifacts/` — A's says where to write it, B's says where to read it and that it's required input, not optional context. `plan.json`'s `description` field is prose, not a handoff mechanism.

**Provider-neutral checkpoints and provider-specific notifications — never conflate them:**
| Status | For | Answered by | Terminal? |
|---|---|---|---|
| `awaiting-authorization` | merge or another-branch push | User directly; main agent relays only for headless mode | No |
| `awaiting-user-input` | work-detail discussion or user judgment | User directly; main agent relays only for headless mode | No |
| `awaiting-main-agent` | integrated instructions, cross-task context, or coordinator action | Main agent | No |
| Provider fast question | non-blocking integrated/context question | Main agent | Not a status transition |
| `watch-plan-status.py` event | every Plan status-file content transition, for every agent kind | Main agent; authoritative scheduling signal | Mirrors the persisted status and drives ready-wave recomputation |
| live status notification | any agent reaches `done`/`failed`/a checkpoint | `report-task-status.py` writes first, then calls shared transport | Best-effort notification; durable status remains authoritative |

A task unsure which applies walks `plan-mechanics.md`'s "Escalation order for a stuck task" (full order there, not restated here). `awaiting-authorization` sits outside that order — it's the merge/other-branch-push readiness gate, not a response to being stuck; a push of the task's own feature branch needs no gate at all. Interactive `awaiting-*` checkpoints work for every supported `herdr-pane` kind. Claude also uses `notifying-main-agent`; Codex relies on the provider-neutral status event and its recorded Herdr terminal identity.

**Same-task continuation — a task_id with a later phase coming isn't finished, don't wrap it up yet.** When a just-finished session has more of the *same* logical task_id coming (never a different, independent task), withhold `wrap-up-task.py` for it — that call atomically archives the instruction and marks the task done in `plan.json`, which would strand phase 2's own instruction lookup and mark the task complete prematurely. Reuse the session through the provider-specific continuation command in `plan-mechanics.md`; phase 2 must restate the provider-neutral status-report command. The watcher detects the later rewrite of the same status file because it deduplicates by content revision, not filename.

**Status-event coverage (authoritative for Plan scheduling).** Start a `Monitor` running `watch-plan-status.py --plan <slug>`. It emits every content transition — `done`, `failed`, `cancelled`, `awaiting-authorization`, `awaiting-user-input`, `awaiting-main-agent` — including a later overwrite of the same task file. `report-task-status.py --instruction-path` writes before sending the primary herdr notification; a fresh watcher still emits current persisted states once for recovery. On terminal events, auto-detach only after checking for same-task continuation, then recompute and dispatch the next ready wave. Non-terminal events keep the task attached; resolve `awaiting-main-agent` with `reply-to-worker.py`.

**Progress visibility.** A dispatched task may call `report-progress.py --instruction-path <path> --note "<text>"` at any point during its work — a separate, non-notifying, append-only log (`dispatch-mechanics.md`'s "Reporting scripts"). `peeking-work` reads this trail before joining a task's live pane, so checking on a task usually doesn't require interrupting it.

**Shared-resource coordination.** When known coordination state identifies a
resource shared by concurrent tasks, include that constraint and point the
worker to `references/shared-resource-coordination.md`. The worker resolves the
app's concrete resource identity, claims immediately before use, and releases
afterward.

**Verification:** every ready-wave task dispatched together; a task with unresolved dependencies never dispatched early; worktree verified before dispatch; `wrap-up-task.py` withheld for any task_id with a same-task continuation coming, checked before it's ever called, not after; plan completion judged by all tasks terminal, never by the first.

## Branch: List outstanding instructions

Scan `~/.straw-boss/dispatch/` for `<app>--<slug>.json` instruction files only — excluding `archive/`, and excluding a standalone dispatch's own `<app>--<slug>.status.json`/`.progress.jsonl` siblings (per `dispatch-mechanics.md`'s "Reporting scripts"), which match a naive `*.json`/`*.jsonl` glob but are not instructions themselves — reading one as if it were would report a phantom, already-terminal entry that never actually gets wrapped up (`wrap-up-task.py` archives them alongside their real instruction, not standalone). Report grouped by status. Pure read.

## Branch: Wrap up an instruction

1. Confirm which instruction (ask if ambiguous).
2. If `herdr-pane` and its worker pane is still open and no longer needed, close
   that pane. The coordinator's shared tab remains open. `claude-p` has nothing
   to close.
3. Call `wrap-up-task.py` — sets `wrapped-up`, archives the instruction file and, if present, its `.status.json`/`.progress.jsonl` siblings (per `dispatch-mechanics.md`'s "Reporting scripts") together, and for a plan task syncs `plan.json` to the terminal status read from that task's own status file. Refuses if a status record exists and isn't yet terminal (`done`/`failed`/`cancelled`) — for a plan task from its `status/<task_id>.json`, for a standalone dispatch from its own `.status.json` if one was ever written (no record at all is not itself a refusal — an older dispatch, or a `claude-p` one confirmed done by process exit, may legitimately have none). Never `mv`/`Edit` this by hand.

**Verification:** the worker pane is confirmed closed before the file is archived;
the coordinator pane and shared tab remain open.
