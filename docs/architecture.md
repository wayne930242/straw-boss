# Architecture

Design rationale for straw-boss — read this if you're extending the plugin, not if you're just using it (start with the README instead).

## Why app-rooted workrooms, not a condensed summary

App-rooted workrooms are the plugin's core value when a separate session is useful. That value is independent of app count: it applies to one app in a single-app repo as well as one app in a monorepo. Routing across multiple apps (`work-on`) is an additional layer, not what makes a workroom worthwhile.

Path-scoped rules and nested `CLAUDE.md` files already reach a session working from a main agent's own root reactively, once a matching file is touched. What doesn't reach it: an app's own `.claude/skills/` and `.claude/settings.json` hooks, which only load for a session whose root is that app's own directory. A session working on an app from somewhere else has never actually triggered that app's own hooks, and never sees its own skills.

Opening a session rooted in the app closes that gap directly, instead of hand-maintaining a summary of what the app's own rules say. A condensed digest drifts the moment the app's real rules change and duplicates content the app's own files already state authoritatively. Claude Code and Codex CLI workers both begin from the target app's real directory; Claude Code also loads the app's own skills and hooks there.

That gap can make a separate workroom worth its coordination cost, whether the work is implementation, an audit, research, or diagnosis. A bounded task the current agent can carry end to end stays in the current loop and loads the target checkout's instructions before acting.

## The smallest sufficient loop

`boss-say` selects one of three coordination graphs from how the work actually runs:

- **single-loop** — the current agent carries one bounded item end to end, loading the target checkout's instructions before it acts.
- **sub-agent fan-out/fan-in** — clear, independent branches run in subagents and return to the current agent for integration.
- **orchestrator-worker** — multiple app-rooted workers run under one event-driven coordination loop. This is the only graph that writes a dispatch plan.

A single item may also get a separate app-rooted workroom without becoming an orchestrator-worker graph. That is still a single-loop: one lifecycle owner drives one worker's dispatch, checkpoints, and cleanup. A separate workroom is selected for durable interaction, continuation, or an app ownership boundary, not merely because the task reads managed-app files.

Once a separate workroom is selected, transport is an independent environment choice. `dispatching-work` uses a watchable, joinable `herdr-pane` when enabled and available, and a headless worker otherwise. The worker provider is orthogonal: Claude Code is the fallback, while an explicit setup, project work route, or app default can select Codex CLI. Standalone, batch, and dependency-tracked tasks all use provider-neutral status files and lifecycle scripts.

## Components

This table is what each skill *does*; see `docs/roles.md` for who's doing it — the user/main agent/dispatched agent/subagent cast, not repeated here.

| Component | Kind | Role |
|---|---|---|
| `work-on` | skill (invoked internally by every specialist skill) | Classify a request against the project's configured apps (`.claude/straw-boss/apps.json`) or the implicit root of a single-app repository, apply any configured legacy redirect; for implementation work, decompose into a Plan when it's more than one task (confirmed with the user), then return the resolution to the caller. It does not run the target app's development or SDD process |
| `dispatching-work` | skill (internal machinery, fronted by `boss-say`) | Pick the transport and, independently, resolve the complete work route (agent kind, provider profile, model, effort, and optional Claude advisor), write/track dispatch instructions, execute standalone/batch/Plan waves, list outstanding dispatches, and wrap them up |
| `dispatch-task.py` + `launch-dispatched-agent.py` | public scripts | Generate an immutable per-dispatch contract, name the shared coordinator tab before splitting and the worker pane before prompting, record and apply the resolved provider profile/model/effort plus Claude-only advisor, inject the lifecycle contract, confirm the initial task reached the transcript before recording a launch receipt, and refuse identity divergence or unsupported Codex advisor |
| `run-headless-dispatched-agent.py` | public script | Claim one instruction, start headless Claude or Codex with the generated contract, persist Codex's provider thread identity, and resume only a recorded Codex checkpoint while requiring its next status revision |
| `bringing-coworker` + `dispatch-coworker.py` | skill + public script | Authenticate an in-progress worker and bring one review-only or file-disjoint Claude Code or Codex CLI coworker into its exact worktree and shared tab through the existing write/launch/confirm adapters |
| `handoff-orchestrator` + `handoff-orchestrator.py` | skill + public script | After one explicit user approval, open and label an independent Herdr tab, pass a bounded continuity payload, verify receiver acceptance, and transfer that scope into the receiver's `boss-say` loop. Failed acceptance closes the new tab and leaves ownership at the source |
| `dispatch_transport.py` + `send-dispatch-message.py` | internal module + public script | Resolve sender and receiver, validate sessions/intent, enforce a two-sentence delta, carry structured references, submit through herdr, and retain content-free correlation proof. Status/checkpoint wrappers reuse this seam |
| `dispatched-agent-stop-guard.py` | Claude Stop hook | Block an in-progress dispatched Claude session from ending a turn without a durable checkpoint or terminal report; non-dispatched sessions are unaffected |
| `peeking-work` | skill | Read-only peek at one dispatch's actual live content — a herdr pane's recent output or a headless task's transcript tail — without joining or interrupting it. Used by `dispatching-work`'s failure diagnosis and `boss-say`'s stalled-batch reporting; every other skill that needs this calls it too, instead of reimplementing the read |
| `notifying-main-agent` | skill (invoked by a dispatched agent, not the main agent) | Routes integrated/context questions and status through instruction-keyed scripts; the independent worker and user own work details. `done`/`failed` persist before notifying the main-agent Herdr endpoint, and the watcher remains recovery evidence. |
| `asking-peer-agents` | skill (invoked by a dispatched agent, not the main agent) | Reads a resolved peer's progress first, then uses authenticated question/answer messages with correlation ids; peers exchange facts, never direction or authorization. |
| `init` | skill (user-invoked, one-time/occasional setup) | Ask which apps to manage, write `apps.json` and sync root `CLAUDE.md`; configure project work routes with provider profile/model/effort and optional Claude Code native advisor; record whether herdr-backed dispatch is enabled; check each app for a missing agent system and, on confirmation, dispatch `create-great-harness` into it |
| `create-great-harness` | skill (dispatched by `init`, or invoked directly) | Lightweight agent-system bootstrap for an app that has neither `CLAUDE.md` nor app guidance under `.claude/`: an evidence-grounded `CLAUDE.md` is the baseline; a hook or skill-authoring rule is added only when the confirmed scope or concrete project evidence calls for it |
| `boss-say` | skill (**the** entry point) | Every request comes here — implementation, audit, research, or diagnosis. Selects the owning skill and smallest sufficient loop for one item, a capped batch, or a self-paced backlog, then carries bounded work or invokes the needed coordination mechanics |
| `i-am-orchestrator` | injected main-agent skill | Keep dispatched lifecycles event-driven, surface only coordination deltas, and leave work definition to each dispatched agent and the user inside the named reality anchor |
| `choosing-graph` | skill (a main agent or a dispatched worker invokes it before work starts) | Name the coordination graph — single-loop, sub-agent fan-out/fan-in, or the orchestrator-worker that dispatches more than one app-rooted worker and alone writes `plan.json` — and the reality anchor that will prove the result: testing, pseudo-human, human, or an independent agent's adversarial review. The anchor names the category and its checkpoint; the seam, cases, and tools inside it stay with the worker and the user. A frontend human/pseudo-human anchor gets its port claimed at dispatch |
| `shipping-task` | skill (a specialist `boss-say` drives) | Implementation lifecycle for **one** task, picked per task from how the user regards the work: team-mode (worktree → develop → MR → merge → archive) or solo-mode (direct commit to base) — delegated to the target app's own `gitWorkflowSkill` where configured, else this skill's fallback steps; commits freely in either mode, pushes its own feature branch freely too (reported, not gated), and gates merge (and any push outside its own feature branch) on explicit user authorization |
| `inspecting-app` | skill (a specialist `boss-say` drives) | Resolve the app, choose the smallest sufficient loop, and return an evidence-bearing rules/conventions audit; a confirmed lower-tier route may carry a bounded audit |
| `investigating-app` | skill (a specialist `boss-say` drives) | Resolve the app, choose the smallest sufficient loop, and explain current behavior/mechanism/impact with evidence references rather than returning a binary answer |
| `troubleshooting-app` | skill (a specialist `boss-say` drives) | Classify from supplied evidence; ordinary failures keep diagnosis and repair in one `shipping-task` loop, while an integration diagnosis needed to route or schedule later work runs as a separate preflight investigation |

`inspecting-app`/`investigating-app` use the general-purpose audit/research owner available in the active agent setup; those owners are not part of straw-boss. `boss-say`, `shipping-task`, `troubleshooting-app`, and `work-on` stand on their own.

## Why one entry point for everything

Per `docs/roles.md`'s cast: the user owns the requested outcome, while the main
agent owns routing and coordination. In a bounded single-loop it also owns the
work. Once work is dispatched, the launched agent and user own its work details
inside the reality anchor named by the main agent. `boss-say` is the single door
for implementation, audit, research, or diagnosis, and triages two independent
axes:

- **Scale** — one logical item (even one that decomposes into phases or spans several apps) goes to the matching specialist skill; several independent items become a batch, dispatched under a concurrency cap; a batch too large for one turn self-paces, with `boss-say` starting the `/loop` itself.
- **Coordination graph**, per item — single-loop for bounded work, sub-agent fan-out/fan-in for clear branches, or orchestrator-worker for several app-rooted workers. A separate workroom is an execution choice within that graph when durable interaction, continuation, or app ownership makes it useful.

Both are stated, not asked. A user who disagrees overrides it in one sentence, which is cheaper than a question asked on every item.

`shipping-task` and `boss-say`'s batch path cover different shapes of the same underlying lifecycle: one task with an optional internal dependency graph (`work-on`'s own Plan mechanism, still one logical unit of work) versus many separate, independent tasks that happen to be handled together. A batch item is never allowed to depend on another batch item — if one turns out to need its own graph, it comes out of the batch and goes through its matching specialist skill instead.

## Routing rule

1. `boss-say` fires on any request — implementation, audit, research, or diagnosis.
2. Each item resolves its app via `work-on`, which classifies against configured apps and applies any legacy redirect. In a single-app repository without configuration, the repository root can be the implicit app.
3. `boss-say` states the owner, scale, coordination graph, and reality anchor it picked. One bounded logical item stays in the current loop; clear branches may fan out; a durable workroom uses `dispatching-work`; independent batch items run under a cap in this turn or a `/loop` it starts itself.
4. Requests resolving to more than one dependent task get confirmed as a Plan (`work-on` Task 4) before dispatch. A single-task request creates no Plan. The Plan is dispatch structure, not a product or implementation specification.
5. The execution owner loads the target checkout's instructions, then follows that app's development and SDD route. For a separate workroom, the specialist skill assembles a concise brief from the user's intent and verified coordination facts, while target-app discovery stays with the dispatched agent. Investigation, audit, and diagnosis return explanations with evidence references rather than binary answers.
6. Interactive tasks discuss work details and authorization directly with the user in their own pane; `shipping-task` points the user there. Headless tasks persist the same checkpoint so the main agent can relay the user's answer without deciding for them. Commit and task-feature-branch pushes need no authorization; the latter is a non-blocking FYI. A dispatched diagnosis reports root cause through the shared completion-status command, which writes before notifying the main agent's validated herdr endpoint.
7. `dispatching-work`'s wrap-up closes the finished worker pane and instruction
   while preserving the coordinator's shared tab; team-mode worktree removal
   remains the main agent's job. Status and close-out requests go through
   `boss-say` into the List/Wrap-up branches.

## Why the app list is project config, not plugin code

Everything that used to be hardcoded per app (the routing table, legacy redirects, forbid-direct-commit rules, per-app git-workflow skills, gitignored local files a worktree needs, cross-app coordination pointers) is real knowledge about *your* project, not about straw-boss. `init` asks for it once and writes it to `.claude/straw-boss/apps.json` (schema: `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md`) plus a synced section in your project's root `CLAUDE.md`. Without that config, `work-on` can infer only the root of a repository that clearly contains one app; monorepo routing and per-app policy come from the project's config.

## State: project config vs. machine state

- **`.claude/straw-boss/apps.json`** — project-level, checked into git, shared with the team. Which apps exist, how to route to them, their per-app quirks.
- **`~/.straw-boss/capability.json`, `~/.straw-boss/dispatch/`, `~/.straw-boss/plans/`** — per-user, per-machine operational state, outside any git checkout. Whether herdr-backed dispatch is enabled on this machine, what's currently dispatched, in-flight plans.

## External mutations stay gated

Merge, and a push landing outside the task's own feature branch (a monorepo-root submodule pointer-bump, an app-owned git-workflow skill's protected-branch release push), require explicit user authorization, every time — an agent cannot self-authorize either. Interactive dispatched agents obtain that authorization directly in their own pane. Headless Codex persists the checkpoint for faithful relay by the main agent; headless Claude exits with a terminal failed note and starts a fresh attempt carrying the answer.

Commit is free — the agent commits on its own as it goes, on either lifecycle shape. So is pushing the task's own feature branch (opening/updating an MR/PR against it): the branch was already implicitly authorized when the main agent created it for this task, so the agent pushes on its own and reports it as a non-blocking FYI, then keeps working — never a stop. `forbidDirectCommit` is the one remaining gate on solo-mode's direct commit to a shared base branch. Tracker-ticket mutations follow the same rule: an agent never touches a ticket, only the main agent does, once a whole plan (not just one task) is actually complete.

See `skills/dispatching-work/references/` for the exact mechanics (dispatch, plan, cross-session coordination) — this document covers the *why*, those cover the *how*.
