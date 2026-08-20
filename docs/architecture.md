# Architecture

Design rationale for straw-boss — read this if you're extending the plugin, not if you're just using it (start with the README instead).

## Why dispatch, not a condensed summary

This is the plugin's core value, independent of app count — it applies to a single-app repo dispatched from a main agent's own cwd just as much as to any one app in a monorepo. Routing across multiple apps (`work-on`) is an additional layer on top for monorepos, not what makes dispatch itself worthwhile.

Path-scoped rules and nested `CLAUDE.md` files already reach a session working from a main agent's own root reactively, once a matching file is touched. What doesn't reach it: an app's own `.claude/skills/` and `.claude/settings.json` hooks, which only load for a session whose root is that app's own directory. A session working on an app from somewhere else has never actually triggered that app's own hooks, and never sees its own skills.

Dispatching into a session rooted in the app closes that gap directly, instead of hand-maintaining a summary of what the app's own rules say. A condensed digest drifts the moment the app's real rules change, and duplicates content the app's own files already state authoritatively. straw-boss dispatches the *work*, not a description of the work.

That gap is what makes dispatch worth its cost — not whether the work happens to be read-only. An audit, a piece of research, or a diagnosis benefits from the app's own harness exactly as much as a code change does, whenever it actually needs that harness. `boss-say` judges each item on that basis, not on its type.

## Two tiers of execution

Every item `boss-say` triages lands on one of two tiers:

- **Subagent** — a plain Claude Code subagent, no app-dir rooting, for anything that doesn't need the target app's own harness: a self-contained question, a lookup, something a capable agent can just do.
- **Dispatched agent** — a session rooted in the app's own directory, run through `dispatching-work`, for anything that needs the app's actual skills/hooks/rules loaded: real code changes, an audit against the app's real rule source, research into its actual current behavior, diagnosis using its own logs and tests.

The one thing that costs something here is judging it wrong in one direction — going solo, in this session, on an item that actually needed the app's harness. Dispatching something that turns out trivial, or keeping something solo that turns out to need more digging, are both fine outcomes of a reasonable call.

Within the dispatched tier, transport is a separate, environment-driven choice, not a per-item one: `dispatching-work` picks `herdr-pane` whenever the environment supports it (a watchable, joinable pane that can pause for a live reply), and falls back to headless `claude -p` only when herdr genuinely isn't available this session.

## Components

This table is what each skill *does*; see `docs/roles.md` for who's doing it — the user/main agent/dispatched agent/subagent cast, not repeated here.

| Component | Kind | Role |
|---|---|---|
| `work-on` | skill (invoked internally by every specialist skill) | Classify a request against the project's configured apps (`.claude/straw-boss/apps.json`), apply any configured legacy redirect; for implementation work, decompose into a Plan when it's more than one task (confirmed with the user), then hand back to the caller for `boss-say`'s execution-tier call |
| `dispatching-work` | skill (internal machinery, fronted by `boss-say`) | Pick the transport (`herdr-pane` whenever available, `claude-p` as the environment fallback), write/track dispatch-instruction files under the user's home directory (`~/.straw-boss/dispatch/` — per-machine state, not project config), execute single dispatches or a whole Plan's wave-by-wave dispatch (`~/.straw-boss/plans/`), list outstanding dispatches, wrap one up |
| `peeking-work` | skill | Read-only peek at one dispatch's actual live content — a herdr pane's recent output, or a `claude-p` task's transcript tail — without joining or interrupting it. Used by `dispatching-work`'s failure diagnosis and `boss-say`'s stalled-batch reporting; every other skill that needs this calls it too, instead of reimplementing the read |
| `notifying-main-agent` | skill (invoked by a dispatched agent, not the main agent) | The agent-side counterpart to cross-session coordination: given how to reach the main agent (stated in the dispatch instruction — a herdr pane id, a `SendMessage` peer name, or both), send it a purely informational report or question — herdr first and `SendMessage` as fallback (or as the only channel for `claude-p`, fire-and-forget) — with the judgment rule for what counts as informational and the never-treat-a-reply-as-authorization safety boundary. A dispatched diagnosis reports its root cause this way (or via its own completion note); deciding what happens next stays with the session that dispatched it |
| `init` | skill (user-invoked, one-time/occasional setup) | Ask which apps to manage, write `apps.json` and sync root `CLAUDE.md`; record whether herdr-backed dispatch is enabled (before the bootstrap check below, so its dispatch decision has real capability info to work with); check each app for a missing agent system and, on confirmation, dispatch `create-great-harness` into it |
| `create-great-harness` | skill (dispatched by `init`, or invoked directly) | Lightweight agent-system bootstrap for an app that has neither `CLAUDE.md` nor `.claude/`: a short, non-obvious-content-only `CLAUDE.md`, one pipe-tested guard hook (default: block force-push/hard-reset on the primary branch), and one skill-authoring rule pulled live from the official Claude Code docs rather than hand-maintained prose. Deliberately not a full skills scaffold or rules library — those earn their place once there's real content; the skill-authoring rule is the one exception, since it costs nothing to keep current |
| `boss-say` | skill (**the** entry point) | Every request comes here — implementation, audit, research, or diagnosis. Triages scale (one item, a capped batch, or a self-paced batch) and execution tier (subagent or dispatched agent) per item, then hands off to the matching specialist skill or its own batch mechanics |
| `shipping-task` | skill (a specialist `boss-say` drives) | Implementation lifecycle for **one** task, user-picked per task: full flow (worktree → develop → MR → merge → archive) or light flow (direct commit to base) — delegated to the target app's own `gitWorkflowSkill` where configured, else this skill's fallback steps; commits freely on either flow, and gates push/merge on explicit user authorization |
| `inspecting-app` | skill (a specialist `boss-say` drives) | Resolve the app, then run your own rules/conventions audit skill — solo in this session, or dispatched into the app, per `boss-say`'s tier call; a dispatched worker decides for itself whether to run an app-local audit skill or the global one |
| `investigating-app` | skill (a specialist `boss-say` drives) | Resolve the app, then run your own research skill — solo or dispatched, same tier call; a dispatched worker decides for itself which research skill to run |
| `troubleshooting-app` | skill (a specialist `boss-say` drives) | Diagnose a reported failure (app-code vs. infrastructure) — solo or dispatched, same tier call — then hand the fix back to `boss-say` once root cause is known |

`inspecting-app`/`investigating-app` hand off to general-purpose audit/research skills that aren't part of straw-boss — they're expected to already exist in your own Claude Code setup (most setups have something like this). If you don't have equivalents, those two specialists have nothing to hand off to; `boss-say`, `shipping-task`, `troubleshooting-app`, and `work-on` stand on their own.

## Why one entry point for everything

Per `docs/roles.md`'s cast: the user hands over work, the main agent decides how it gets done. `boss-say` is the single door for anything — implementation, audit, research, or diagnosis — and its first act is triage, on two independent axes:

- **Scale** — one logical item (even one that decomposes into phases or spans several apps) goes to the matching specialist skill; several independent items become a batch, dispatched under a concurrency cap; a batch too large for one turn self-paces, with `boss-say` starting the `/loop` itself.
- **Execution tier**, per item — a plain subagent when the app's own harness isn't needed, a dispatched agent when it is. This is judged fresh per item, never defaulted from what kind of work it is.

Both are stated, not asked. A user who disagrees overrides it in one sentence, which is cheaper than a question asked on every item.

`shipping-task` and `boss-say`'s batch path cover different shapes of the same underlying lifecycle: one task with an optional internal dependency graph (`work-on`'s own Plan mechanism, still one logical unit of work) versus many separate, independent tasks that happen to be handled together. A batch item is never allowed to depend on another batch item — if one turns out to need its own graph, it comes out of the batch and goes through its matching specialist skill instead.

## Routing rule

1. `boss-say` fires on any request — implementation, audit, research, or diagnosis.
2. Each item resolves its app via `work-on` (classifying against the configured apps, applying any legacy redirect); `boss-say` then judges the execution tier — solo in this session against the app's real files, or dispatched into a session rooted there.
3. `boss-say` states the scale shape it picked: one logical item → the matching specialist skill; many independent items → its own capped batch, run in this turn or under a `/loop` it starts itself.
4. Implementation work has every resolved app checked for an already-open, related OpenSpec change (`work-on` Task 4) before any task description is written — the user decides whether it's in scope. Requests resolving to more than one task then get confirmed as a Plan (`work-on` Task 5) before anything is dispatched; a single-task request skips straight to dispatch.
5. The specialist skill (or `boss-say` for a batch item) assembles each task's description — pointing at an existing OpenSpec change by name where Task 4 found and confirmed one, never restating its scope — and invokes `dispatching-work` when the tier call landed on dispatch (single instruction, or the whole Plan), which picks the transport per environment and executes in sessions rooted in the target app(s).
6. `shipping-task` obtains user authorization for every push/merge each agent reaches (reported as `awaiting-authorization`, not silence), resuming it to proceed rather than letting it self-authorize; commit itself needs none. It does the same for any tracker ticket tied to the work. A substantive work-content question (`awaiting-user-input`) is different — `shipping-task` only points the user at the task's own pane, it does not relay or resume. A dispatched diagnosis is different again: it reports root cause through its own completion or `notifying-main-agent`, and the session that dispatched it decides whether to hand off to `boss-say` for the fix.
7. `dispatching-work`'s wrap-up (single task) or auto-detach (Plan, on each task reaching `done`/`failed`/`cancelled`) closes a finished instruction and any herdr pane/tab it used; for a full-flow task, worktree removal is the main agent's job too, paired with its main-agent-created worktree. A user's own status question or close-out request for one dispatch goes through `boss-say`, which calls `dispatching-work`'s List/Wrap-up branches directly.

## Why the app list is project config, not plugin code

Everything that used to be hardcoded per app (the routing table, legacy redirects, forbid-direct-commit rules, per-app git-workflow skills, gitignored local files a worktree needs, cross-app coordination pointers) is real knowledge about *your* project, not about straw-boss. `init` asks for it once and writes it to `.claude/straw-boss/apps.json` (schema: `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md`) plus a synced section in your project's root `CLAUDE.md`. The plugin ships with no apps configured — every routing decision comes from your project's own config, never a default guess.

## State: project config vs. machine state

- **`.claude/straw-boss/apps.json`** — project-level, checked into git, shared with the team. Which apps exist, how to route to them, their per-app quirks.
- **`~/.straw-boss/capability.json`, `~/.straw-boss/dispatch/`, `~/.straw-boss/plans/`** — per-user, per-machine operational state, outside any git checkout. Whether herdr-backed dispatch is enabled on this machine, what's currently dispatched, in-flight plans.

## External mutations stay gated

Push and merge require explicit user authorization, every time — an agent cannot self-authorize either one. `shipping-task`'s dispatch instructions tell the agent to stop and report readiness once it's ready to push or merge, and `shipping-task` (interactive with the actual user) obtains authorization and resumes it. This holds for both dispatch modes.

Commit itself is free — the agent commits on its own as it goes, on either lifecycle shape. `forbidDirectCommit` is the one remaining gate on the light flow's direct commit to a shared base branch. Tracker-ticket mutations follow the push/merge rule: an agent never touches a ticket, only the main agent does, once a whole plan (not just one task) is actually complete.

See `skills/dispatching-work/references/` for the exact mechanics (dispatch, plan, cross-session coordination) — this document covers the *why*, those cover the *how*.
