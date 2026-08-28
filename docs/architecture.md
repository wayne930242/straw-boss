# Architecture

Design rationale for straw-boss — read this if you're extending the plugin, not if you're just using it (start with the README instead).

## Why dispatch, not a condensed summary

This is the plugin's core value, independent of app count — it applies to a single-app repo dispatched from a main agent's own cwd just as much as to any one app in a monorepo. Routing across multiple apps (`work-on`) is an additional layer on top for monorepos, not what makes dispatch itself worthwhile.

Path-scoped rules and nested `CLAUDE.md` files already reach a session working from a main agent's own root reactively, once a matching file is touched. What doesn't reach it: an app's own `.claude/skills/` and `.claude/settings.json` hooks, which only load for a session whose root is that app's own directory. A session working on an app from somewhere else has never actually triggered that app's own hooks, and never sees its own skills.

Dispatching into a session rooted in the app closes that gap directly, instead of hand-maintaining a summary of what the app's own rules say. A condensed digest drifts the moment the app's real rules change, and duplicates content the app's own files already state authoritatively. straw-boss dispatches the *work*, not a description of the work.

That gap is what makes dispatch worth its cost — not whether the work happens to be read-only. An audit, a piece of research, or a diagnosis benefits from the app's own harness exactly as much as a code change does, whenever it actually needs that harness. `boss-say` judges each item on that basis, not on its type.

## Two tiers of execution

Every item `boss-say` triages lands on one of two tiers:

- **Subagent** — a plain subagent, no app-dir rooting, for self-contained or external work that reads nothing under a managed app root.
- **Dispatched agent** — a session rooted in the app's own directory, run through `dispatching-work`, for anything that needs the app's real working directory: real code changes, an audit against the app's real rule source, research into its actual current behavior, diagnosis using its own logs and tests. When the dispatched session runs under the default `claude` agent kind, that also means the app's actual skills/hooks/rules get loaded; a session dispatched under a different, configured agent kind (`dispatching-work`'s own agent-kind resolution) works from the task instruction and the app's own non-Claude-Code conventions instead, without that harness. Both kinds can be standalone, batch, or dependency-tracked Plan tasks because Plan state is reported through provider-neutral scripts rather than a provider-specific mailbox.

The hard boundary is managed-app access: once an item needs to read under an app
root, continuing solo would load that app's context into the wrong session, so it
dispatches at that point. Dispatching something that turns out trivial is safe.

Within the dispatched tier, transport is a separate, environment-driven choice, not a per-item one: `dispatching-work` picks `herdr-pane` whenever the environment supports it (a watchable, joinable pane that can pause for a live reply), and falls back to headless `claude -p` only when herdr genuinely isn't available this session. Which agent CLI runs inside that transport is a further, orthogonal choice — `claude` by default, resolved otherwise from the target app's own configuration or an explicit override (`dispatching-work`'s own agent-kind resolution) — independent of the transport pick.

## Components

This table is what each skill *does*; see `docs/roles.md` for who's doing it — the user/main agent/dispatched agent/subagent cast, not repeated here.

| Component | Kind | Role |
|---|---|---|
| `work-on` | skill (invoked internally by every specialist skill) | Classify a request against the project's configured apps (`.claude/straw-boss/apps.json`), apply any configured legacy redirect; for implementation work, decompose into a Plan when it's more than one task (confirmed with the user), then hand back to the caller for `boss-say`'s execution-tier call. It does not run the target app's development or SDD process |
| `dispatching-work` | skill (internal machinery, fronted by `boss-say`) | Pick the transport and, independently, resolve the complete work route (agent kind, provider profile, model, effort, and optional Claude advisor), write/track dispatch instructions, execute standalone/batch/Plan waves, list outstanding dispatches, and wrap them up |
| `dispatch-task.py` + `launch-dispatched-agent.py` | public scripts | Generate an immutable per-dispatch contract, record and apply the resolved provider profile/model/effort plus Claude-only advisor, inject the lifecycle contract, confirm the initial task reached the transcript before recording a launch receipt, and refuse identity divergence or unsupported Codex advisor |
| `dispatch-coworker.py` | public script | Authenticate an in-progress worker and bring one review-only or file-disjoint coworker into its exact worktree and shared tab through the existing write/launch/confirm adapters |
| `dispatch_transport.py` + `send-dispatch-message.py` | internal module + public script | Resolve sender and receiver, validate sessions/intent, enforce a two-sentence delta, carry structured references, submit through herdr, and retain content-free correlation proof. Status/checkpoint wrappers reuse this seam |
| `dispatched-agent-stop-guard.py` | Claude Stop hook | Block an in-progress dispatched Claude session from ending a turn without a durable checkpoint or terminal report; non-dispatched sessions are unaffected |
| `peeking-work` | skill | Read-only peek at one dispatch's actual live content — a herdr pane's recent output, or a `claude-p` task's transcript tail — without joining or interrupting it. Used by `dispatching-work`'s failure diagnosis and `boss-say`'s stalled-batch reporting; every other skill that needs this calls it too, instead of reimplementing the read |
| `notifying-main-agent` | skill (invoked by a dispatched agent, not the main agent) | Routes integrated/context questions and status through instruction-keyed scripts; the independent worker and user own work details. `done`/`failed` persist before notifying the main-agent Herdr endpoint, and the watcher remains recovery evidence. |
| `asking-peer-agents` | skill (invoked by a dispatched agent, not the main agent) | Reads a resolved peer's progress first, then uses authenticated question/answer messages with correlation ids; peers exchange facts, never direction or authorization. |
| `init` | skill (user-invoked, one-time/occasional setup) | Ask which apps to manage, write `apps.json` and sync root `CLAUDE.md`; configure project work routes with provider profile/model/effort and optional Claude Code native advisor; record whether herdr-backed dispatch is enabled; check each app for a missing agent system and, on confirmation, dispatch `create-great-harness` into it |
| `create-great-harness` | skill (dispatched by `init`, or invoked directly) | Lightweight agent-system bootstrap for an app that has neither `CLAUDE.md` nor app guidance under `.claude/`: an evidence-grounded `CLAUDE.md` is the baseline; a hook or skill-authoring rule is added only when the confirmed scope or concrete project evidence calls for it |
| `boss-say` | skill (**the** entry point) | Every request comes here — implementation, audit, research, or diagnosis. Triages scale (one item, a capped batch, or a self-paced batch) and execution tier (subagent or dispatched agent) per item, then hands off to the matching specialist skill or its own batch mechanics |
| `choosing-graph` | skill (a main agent or a dispatched worker invokes it before work starts) | Name the coordination graph — single-loop, sub-agent fan-out/fan-in, or the orchestrator-worker that dispatches more than one app-rooted worker and alone writes `plan.json` — and the reality anchor that will prove the result: testing, pseudo-human, human, or an independent agent's adversarial review. The anchor names the category and its checkpoint; the seam, cases, and tools inside it stay with the worker and the user. A frontend human/pseudo-human anchor gets its port claimed at dispatch |
| `shipping-task` | skill (a specialist `boss-say` drives) | Implementation lifecycle for **one** task, picked per task from how the user regards the work: team-mode (worktree → develop → MR → merge → archive) or solo-mode (direct commit to base) — delegated to the target app's own `gitWorkflowSkill` where configured, else this skill's fallback steps; commits freely in either mode, pushes its own feature branch freely too (reported, not gated), and gates merge (and any push outside its own feature branch) on explicit user authorization |
| `inspecting-app` | skill (a specialist `boss-say` drives) | Resolve the app, then dispatch an evidence-bearing rules/conventions audit into it; a confirmed lower-tier route is allowed for bounded audits |
| `investigating-app` | skill (a specialist `boss-say` drives) | Resolve the app, then dispatch current-state research that explains behavior/mechanism/impact with evidence references rather than returning a binary answer |
| `troubleshooting-app` | skill (a specialist `boss-say` drives) | Classify from supplied evidence; ordinary failures keep diagnosis and repair in one `shipping-task` worker, while an integration diagnosis needed to route or schedule later dispatches runs as a separate preflight investigation |

`inspecting-app`/`investigating-app` hand off to general-purpose audit/research skills that aren't part of straw-boss — they're expected to already exist in your own Claude Code setup (most setups have something like this). If you don't have equivalents, those two specialists have nothing to hand off to; `boss-say`, `shipping-task`, `troubleshooting-app`, and `work-on` stand on their own.

## Why one entry point for everything

Per `docs/roles.md`'s cast: the user hands over work, the main agent decides how
to dispatch it, and the launched agent decides how to execute it with the user.
`boss-say` is the single door for anything—implementation, audit, research, or
diagnosis—and its first act is triage on two independent axes:

- **Scale** — one logical item (even one that decomposes into phases or spans several apps) goes to the matching specialist skill; several independent items become a batch, dispatched under a concurrency cap; a batch too large for one turn self-paces, with `boss-say` starting the `/loop` itself.
- **Execution tier**, per item — a plain subagent only when no managed-app files are needed; any work that reads under an app root dispatches so that app's agent system loads in its worker instead of the coordinator.

Both are stated, not asked. A user who disagrees overrides it in one sentence, which is cheaper than a question asked on every item.

`shipping-task` and `boss-say`'s batch path cover different shapes of the same underlying lifecycle: one task with an optional internal dependency graph (`work-on`'s own Plan mechanism, still one logical unit of work) versus many separate, independent tasks that happen to be handled together. A batch item is never allowed to depend on another batch item — if one turns out to need its own graph, it comes out of the batch and goes through its matching specialist skill instead.

## Routing rule

1. `boss-say` fires on any request — implementation, audit, research, or diagnosis.
2. Each item resolves its app via `work-on` (classifying against the configured apps, applying any legacy redirect); anything that must read inside a managed app dispatches into a session rooted there. Solo work is limited to self-contained or external work that needs no managed-app files.
3. `boss-say` states the scale shape it picked: one logical item → the matching specialist skill; many independent items → its own capped batch, run in this turn or under a `/loop` it starts itself.
4. Requests resolving to more than one task get confirmed as a Plan (`work-on` Task 4) before anything is dispatched; a single-task request skips straight to dispatch. This plan is dispatch structure, not a product or implementation spec.
5. The specialist skill (or `boss-say` for a batch item) assembles each task's description from the user's intent and invokes `dispatching-work` for managed-app work (single instruction, or the whole Plan). Investigation/audit/diagnosis asks for an explanation with evidence references, not a binary answer, and may use a confirmed lower-tier route. The dispatched agent enters the target app first, then applies that app's own development and SDD route; Straw Boss neither selects nor runs it.
6. Interactive tasks discuss work details and authorization directly with the user in their own pane; `shipping-task` points the user there. Headless tasks persist the same checkpoint so the main agent can relay the user's answer without deciding for them. Commit and task-feature-branch pushes need no authorization; the latter is a non-blocking FYI. A dispatched diagnosis reports root cause through the shared completion-status command, which writes before notifying the main agent's validated herdr endpoint.
7. `dispatching-work`'s wrap-up closes the finished worker pane and instruction
   while preserving the coordinator's shared tab; team-mode worktree removal
   remains the main agent's job. Status and close-out requests go through
   `boss-say` into the List/Wrap-up branches.

## Why the app list is project config, not plugin code

Everything that used to be hardcoded per app (the routing table, legacy redirects, forbid-direct-commit rules, per-app git-workflow skills, gitignored local files a worktree needs, cross-app coordination pointers) is real knowledge about *your* project, not about straw-boss. `init` asks for it once and writes it to `.claude/straw-boss/apps.json` (schema: `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md`) plus a synced section in your project's root `CLAUDE.md`. The plugin ships with no apps configured — every routing decision comes from your project's own config, never a default guess.

## State: project config vs. machine state

- **`.claude/straw-boss/apps.json`** — project-level, checked into git, shared with the team. Which apps exist, how to route to them, their per-app quirks.
- **`~/.straw-boss/capability.json`, `~/.straw-boss/dispatch/`, `~/.straw-boss/plans/`** — per-user, per-machine operational state, outside any git checkout. Whether herdr-backed dispatch is enabled on this machine, what's currently dispatched, in-flight plans.

## External mutations stay gated

Merge, and a push landing outside the task's own feature branch (a monorepo-root submodule pointer-bump, an app-owned git-workflow skill's protected-branch release push), require explicit user authorization, every time — an agent cannot self-authorize either. Interactive dispatched agents obtain that authorization directly in their own pane; headless tasks persist the checkpoint for faithful relay by the main agent.

Commit is free — the agent commits on its own as it goes, on either lifecycle shape. So is pushing the task's own feature branch (opening/updating an MR/PR against it): the branch was already implicitly authorized when the main agent created it for this task, so the agent pushes on its own and reports it as a non-blocking FYI, then keeps working — never a stop. `forbidDirectCommit` is the one remaining gate on solo-mode's direct commit to a shared base branch. Tracker-ticket mutations follow the same rule: an agent never touches a ticket, only the main agent does, once a whole plan (not just one task) is actually complete.

See `skills/dispatching-work/references/` for the exact mechanics (dispatch, plan, cross-session coordination) — this document covers the *why*, those cover the *how*.
