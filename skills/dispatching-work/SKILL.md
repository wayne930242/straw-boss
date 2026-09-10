---
name: dispatching-work
description: Use after boss-say has landed on dispatch and work-on has resolved the target app or plan.
---

## Overview

**Use the smallest sufficient loop.** This skill implements dispatch mechanics once a separate workroom is selected; a launched Herdr agent and the user choose its specification, design, implementation, and the verification method inside the reality anchor the brief names.

**The unit this skill manages is the agent, not the app.** An app (`.straw-boss/apps.json`, resolved upstream by `work-on`) is only *where* an agent is rooted — this skill starts the agent there, tracks it, and closes it out; it never itself decides which app a request belongs to. Every dispatched task is one agent, tracked as one instruction file under `~/.straw-boss/dispatch/` — the user's home directory, not the target project checkout (see `init`).

This skill covers **dispatch** a single agent (Tasks 1-5), **dispatch a plan** (Branch below, when `work-on` produced a multi-task dependency graph — one agent per task), **list**, and **wrap up**. Every requirement below is real, not a pointer to go read something else first.

Exact CLI/JSON syntax lives in `references/`:

- `dispatch-mechanics.md` — single-agent dispatch + permission-mode detection.
- `plan-mechanics.md` — plan/status schemas, worktree repair heredoc, and the provider-neutral status watcher.
- `cross-session-coordination.md` — making the main agent addressable (herdr pane id primary, with provider-specific fast channels), plus mid-task interrupt syntax. For resumed Codex terminal mismatches, follow its single-record rebind path.
- `shared-resource-coordination.md` — a worktree isolates files, not a fixed port or a shared DB another *main agent's* task might collide on. One command per case: `claim-port` for a flexible port, `wait` for a fixed port or DB migration.

For a specific agent's actual live content or progress — not just its status — invoke `peeking-work` instead of reading a pane/transcript inline here.

**Self-compact.** Compact your own context whenever the next turn's needs are already persisted somewhere durable (`plan.json`, an instruction file) rather than sitting only in this turn's reasoning: `herdr agent prompt "$HERDR_PANE_ID" "/compact [focus]"`. This is yours to decide, and it interrupts nothing in flight — mechanics in `cross-session-coordination.md`'s "Self-compact".

## Task 1: Confirm Herdr and the work route

Herdr is required for a dispatch. Confirm `herdr status` succeeds and that the current `$HERDR_PANE_ID` returns a valid live agent record. Where the CLI, the service, or the current pane is missing, report which condition is unmet and ask the user to continue in a Herdr session; create the dispatch once all of them hold. Every dispatch uses `herdr-pane`.

**Resolve the complete worker setup independently of mode** — see `references/dispatch-mechanics.md`'s "Resolving the work route." Take the first of these that applies:

1. An explicit one-off setup.
2. A matching work route in root `AGENTS.md` (read `CLAUDE.md` when it has no routing section).
3. The target app's `apps.json.agentKind`.
4. Claude with provider defaults.

Resolve agent kind, provider profile, model, effort, and the Claude Code native advisor together, and state the resolved setup and why. Codex has no native advisor; refuse that combination instead of substituting a coworker. The same resolution applies to standalone, batch, and Plan tasks; dependency tracking is provider-neutral.

**Resolve the main agent's own provider and reachability before writing the instruction.** Pass `--main-agent-kind` on every dispatch. For `herdr-pane`, read this session's live herdr record and pass `$HERDR_PANE_ID` as `--main-agent-pane-id`, plus the provider fingerprint:

- **Claude** — its exact `agent_session.value` with `--main-agent-session-id`.
- **Codex** — `terminal_id` with `--main-agent-terminal-id`, and any available `agent_session.value` with `--main-agent-session-id`.

The shared transport requires the pane and the provider-selected fingerprint before sending anything. Register this session in the orchestrator directory in the same step through `contacting-orchestrators`, so another coordinator on this machine can name this one and read its one-line scope.

**Verification:** Herdr and the current pane are ready, the worker setup and main-agent fingerprint are confirmed, and the orchestrator-directory record is registered.

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

Invoke `choosing-graph` when the graph and anchor are not fixed yet — every
dispatch arrives here, whether a specialist skill routed it or the user named
one directly. The brief then names the reality anchor it settled on, and the
port number when a frontend human or pseudo-human anchor made the main agent
claim one. Inside the anchor the seam, cases, and tools are the worker's and the
user's. The contract already tells every worker to run the adversarial review an
ordinary programming change carries; the brief says so only when the main agent
runs it instead.

Call `dispatch-task.py write` (schema in `references/dispatch-mechanics.md`) — generates Claude's session id and the provider-specific immutable contract, writes the instruction (`status: pending`), and for a plan task marks `plan.json` `dispatched`, refusing before writing if the task is not `planned`. Pass the worker kind, this session's provider, and the validated pane/provider-fingerprint pair from Task 1. Never hand-write the JSON, contract, or UUID.

**Verification:** every brief statement about the work traces to the user
request, a necessary hint or constraint, or an already-known coordination state;
the coordination this dispatch fixed is the brief's own — the brief names the
anchor it settled on without prescribing the method inside it, and says so when
the main agent runs the adversarial review instead of the worker; target-app
discovery is assigned to the worker; instruction and hashed contract exist with
`pending` status before any agent starts.

## Task 4: Dispatch

Follow `references/dispatch-mechanics.md`. For `herdr-pane`, start and submit the task only through `launch-dispatched-agent.py`; it injects the generated contract before the first model turn, verifies the task reached the transcript with at most one retry, and only then writes the launch receipt it confirms the instruction against.

**Run Herdr dispatch in the foreground.** Invoke `launch-dispatched-agent.py` as a foreground tool call, with `run_in_background: false` where supported, and wait for its exit result. If the harness yields a running session, resume that same call until it exits. Inspect the result before confirming or reporting the dispatch; the worker then runs independently in its Herdr pane.

**Mirror the main agent's own permission mode onto the agent.** Detect it from the main agent's own process args (`ps -p "$CLAUDE_PID" -ww -o args=`, exact detection in the reference) and map it through the agent kind's own permission surface (`references/dispatch-mechanics.md`'s "Mapping permission mode across agent kinds" — a per-kind flag combo, not the identical flag string, for anything other than `claude`). An agent must never end up more tightly gated than the main agent dispatching it.

The interactive launcher confirms the dispatch itself: it refuses unless the launch receipt matches the instruction, contract digest, provider, and pane, then flips the instruction to `in-progress` and records the receipt's pane, tab, and identity fields. Read its result — a launch reporting `"confirmed": false` leaves the running worker unable to report status, and its warning names the `dispatch-task.py confirm` to run.

**Verification:**

- the Herdr launcher ran in the foreground and returned success;
- its result was read and the instruction's status is `in-progress`;
- permission mode was detected and mapped through the resolved agent kind's own permission surface, not hardcoded or skipped;
- pane/tab ids recorded for `herdr-pane`;
- session_id cross-checked against what herdr/the agent reports (or recorded from what it reported, for a kind that can't pre-assign one).

## Task 5: Report, then run the lifecycle on the dispatch's own events

Tell the user what was dispatched, in which mode, and how to find it (instruction path; pane/tab for `herdr-pane`).

From here the dispatch reports itself. Its `report-task-status.py` calls persist each checkpoint and terminal status to the instruction's own `.status.json` sibling and then notify this session's recorded pane, so those events are what the main agent acts on:

- resolve interactive `awaiting-main-agent` with `reply-to-worker.py`;
- point the user at an interactive pane for its user checkpoints;
- wrap up terminal status.

Between events the task is running and the main agent is free for other coordination or the user's conversation. `peeking-work` answers what a task is currently doing when the user asks, or when observed evidence and its recorded status actually disagree.

Keep each user-facing event report to the coordination delta and the minimum context needed to understand it. Work questions and authorization are answered directly in the worker pane; the main agent handles coordination questions only.

## Branch: Dispatch a plan

Plans have their own file formats and a wave-scheduling step Tasks 1-5 don't — don't improvise this by analogy.

**Wave dispatch.** Compute the ready wave (`read-plan-status.py --ready`) and dispatch **every task in it at once** — never serialize an independent task through another task's session because it happens to be idle. Each task still goes through Tasks 1-5 individually (Herdr readiness, instruction, dispatch, confirm), with `plan_id`/`task_id` added.

**Worktree ownership (team-mode tasks).** The main agent creates every worktree itself, for every managed app uniformly, regardless of the app's own tooling — plain `git worktree add`, never `herdr worktree create` (see `plan-mechanics.md`'s "Worktree ownership" for why).

Verify `git rev-parse --show-toplevel` inside it resolves to the worktree's own path — repos with `extensions.worktreeConfig = true` silently don't, regardless of creation method — and repair with a `config.worktree` file if not (exact steps in `plan-mechanics.md`). Never dispatch into an unverified worktree. Record that verified path as `repo_root`; the launcher opens its worker pane beside the coordinator in the same tab.

**Agent naming.** `launch-dispatched-agent.py` derives each task's operator-visible handle from its `--role` when the wave gives one, else its `app`, the same as a standalone dispatch (`dispatch-mechanics.md`'s "Interactive herdr launch") — omit `--name` per task rather than hand-picking one, and pass `--role` on `dispatch-task.py write` whenever the task's own workroom is already known (`plan-mechanics.md`'s "Agent naming"). Communication scripts address the instruction, never this name.

**Cross-task artifacts.** When task B depends on task A and genuinely needs A's output, both dispatch instructions state the exact path under `~/.straw-boss/plans/<slug>/artifacts/` — A's says where to write it, B's says where to read it and that it's required input, not optional context. `plan.json`'s `description` field is prose, not a handoff mechanism.

**Provider-neutral checkpoints and provider-specific notifications — never conflate them:**
| Status | For | Answered by | Terminal? |
|---|---|---|---|
| `awaiting-authorization` | merge or another-branch push | User directly in the worker pane | No |
| `awaiting-user-input` | work-detail discussion or user judgment | User directly in the worker pane | No |
| `awaiting-main-agent` | integrated instructions, cross-task context, or coordinator action | Main agent through reply-to-worker.py | No |
| Provider fast question | non-blocking integrated/context question | Main agent | Not a status transition |
| `watch-plan-status.py` event | every Plan status-file content transition, for every agent kind | Main agent; authoritative scheduling signal | Mirrors the persisted status and drives ready-wave recomputation |
| live status notification | any agent reaches `done`/`failed`/a checkpoint | `report-task-status.py` writes first, then calls shared transport | Best-effort notification; durable status remains authoritative |

A task unsure which applies walks `plan-mechanics.md`'s "Escalation order for a stuck task". A user checkpoint is resolved in the worker pane; a coordination question goes through `reply-to-worker.py`.A push of the task's own feature branch needs no gate. Status events use the shared reporting scripts and Herdr identity validation.

**Same-task continuation — a task_id with a later phase coming isn't finished, don't wrap it up yet.** When a just-finished session has more of the *same* logical task_id coming (never a different, independent task), withhold `wrap-up-task.py` for it: that call atomically archives the instruction and marks the task done in `plan.json`, which would strand phase 2's own instruction lookup and mark the task complete prematurely.

Reuse the session through the provider-specific continuation command in `plan-mechanics.md`; phase 2 must restate the provider-neutral status-report command. The watcher detects the later rewrite of the same status file because it deduplicates by content revision, not filename.

**Status-event coverage (authoritative for Plan scheduling).** Start a `Monitor` running `watch-plan-status.py --plan <slug>`. It emits every content transition — `done`, `failed`, `cancelled`, `awaiting-authorization`, `awaiting-user-input`, `awaiting-main-agent` — including a later overwrite of the same task file. `report-task-status.py --instruction-path` writes before sending the primary herdr notification; a fresh watcher still emits current persisted states once for recovery.

- **Terminal events** — auto-detach only after checking for same-task continuation, then recompute and dispatch the next ready wave.
- **Non-terminal events** — keep the task attached; interactive `awaiting-main-agent` uses `reply-to-worker.py`.

**Progress visibility.** A dispatched task may call `report-progress.py --instruction-path <path> --note "<text>"` at any point during its work — a separate, non-notifying, append-only log (`dispatch-mechanics.md`'s "Reporting scripts"). `peeking-work` reads this trail before joining a task's live pane, so checking on a task usually doesn't require interrupting it.

**Shared-resource coordination.** When known coordination state identifies a
resource shared by concurrent tasks, include that constraint and point the
worker to `references/shared-resource-coordination.md`. The worker resolves the
app's concrete resource identity, claims immediately before use, and releases
afterward.

**Verification:** every ready-wave task dispatched together; a task with unresolved dependencies never dispatched early; worktree verified before dispatch; `wrap-up-task.py` withheld for any task_id with a same-task continuation coming, checked before it's ever called, not after; plan completion judged by all tasks terminal, never by the first.

## Branch: List outstanding instructions

Run `roll-call.py` (`references/dispatch-mechanics.md`'s "Roll call") — it reconciles live herdr agents against `~/.straw-boss/dispatch/` and is a pure read. Never answer this from the instruction files alone: a dispatch record says what was started, not what is still alive, and the reverse is worse — a live pane with no instruction is not evidence of anything.

**Liveness uses the recorded provider session plus `agent_status`; legacy Codex instructions use exact terminal matching.** An idle agent's title falls back to looking like a plain shell prompt; reading that as death is what got one coordinator's live worker declared an orphan and its task dispatched a second time.

**A live agent with no instruction is never proof of an ownerless pane.** A coordinator pane has none by design, and a freshly split worker pane has none until its dispatch reaches `dispatch-task.py write` — the roll call reports both as `unattributed`, meaning "not attributable from this data". Closing one on that reading is how somebody else's just-opened pane gets destroyed.

`--mine` narrows the list to this session's own dispatches when several coordinators share the machine; it never narrows attribution.

## Branch: Wrap up an instruction

1. Confirm which instruction (ask if ambiguous).
2. If `herdr-pane` and its worker pane is still open, close it once its own
   status record already reports a terminal status — that is what "no longer
   needed" means. A non-terminal task's pane stays open: closing it early is
   exactly what would manufacture the closed-pane case Step 4 below exists to
   recover from, so reply to the agent and let it report first instead.
   The coordinator's shared tab remains open.
3. Release any shared-resource lock still held on this instruction — the one the
   main agent claimed at dispatch, and any the worker reported claiming without
   confirming release. `references/shared-resource-coordination.md`'s "Releasing
   every lock on a wrapped-up instruction" covers both; every terminal status
   reaches here.
4. If the instruction's own status record is missing or stuck on a non-terminal
   checkpoint (`awaiting-user-input`, `awaiting-main-agent`,
   `awaiting-authorization`) and its `herdr-pane` worker is confirmed already
   closed — `roll-call.py` reporting it `orphaned`, not a terminal title that
   looks like a shell — run `recover-task-status.py` to write
   an explicit terminal status (`done`/`failed`) and a traceable note yourself.
   This is allowed recovery for exactly this situation, not a shortcut: always
   prefer replying to the agent and letting it call `report-task-status.py` on
   itself while the pane is still reachable, and never pick the status value
   from the pane being closed alone — state `done` or `failed` and why, from
   evidence you can point to. A read-only dispatch, or one whose status record
   is already terminal, skips this step.
5. For a landed programming change whose review is not recorded yet, confirm the completion reference and apply `choosing-graph`'s single review checkpoint before archiving.
6. Call `wrap-up-task.py --app <app> --slug <slug>` (a plan task adds `--plan <slug> --task-id <task_id>`). It sets `wrapped-up`, archives the instruction file and, if present, its `.status.json`/`.progress.jsonl` siblings (per `dispatch-mechanics.md`'s "Reporting scripts") together, and for a plan task syncs `plan.json` to the terminal status read from that task's own status file. Never `mv`/`Edit` this by hand.

   What it refuses, and why those checks carry the weight they do — this script has no sender validation and no herdr dependency by design, so these file-shape checks are the only thing standing between a live worker and a session that never dispatched it:

   - A status record that exists and isn't yet terminal (`done`/`failed`/`cancelled`) — for a plan task from its `status/<task_id>.json`, for a standalone dispatch from its own `.status.json`.
   - A standalone dispatch still `in-progress` with no record at all: that worker has a live pane and writes its own status, so silence means it never reported, not that it finished — Step 4 above is the way through.
   - A missing record is not a refusal for anything else (a `pending` dispatch that never launched has no status record).

**Verification:** the worker pane closes after terminal status; every shared-resource lock on this instruction is released before `wrap-up-task.py` runs; any recovered status carries traceable evidence; a landed change has one confirmed completion reference and one review disposition before archive; the coordinator pane and shared tab remain open.
