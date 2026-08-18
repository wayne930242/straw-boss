# Architecture

Design rationale for straw-boss — read this if you're extending the plugin, not if you're just using it (start with the README instead).

## Why dispatch, not a condensed summary

This is the plugin's core value, independent of app count — it applies to a single-app repo dispatched from an orchestrating cwd just as much as to any one app in a monorepo. Routing across multiple apps (`work-on`) is an additional layer on top for monorepos, not what makes dispatch itself worthwhile.

Path-scoped rules and nested `CLAUDE.md` files already reach a session working from an orchestrating root reactively, once a matching file is touched. What doesn't reach it: an app's own `.claude/skills/` and `.claude/settings.json` hooks, which only load for a session whose root is that app's own directory. A session working on an app from somewhere else has never actually triggered that app's own hooks, and never sees its own skills.

Dispatching into a session rooted in the app closes that gap directly, instead of hand-maintaining a summary of what the app's own rules say. A condensed digest drifts the moment the app's real rules change, and duplicates content the app's own files already state authoritatively. straw-boss dispatches the *work*, not a description of the work.

Read-only requests (`inspecting-app`, `investigating-app`, `troubleshooting-app`'s diagnosis phase) don't have this problem — reading an app's real files directly in the current session isn't limited by the skills/hooks gap dispatch exists to close, so they never dispatch.

## Components

| Component | Kind | Role |
|---|---|---|
| `work-on` | skill (invoked internally by the 4 entry points) | Classify a request against the project's configured apps (`.claude/straw-boss/apps.json`), apply any configured legacy redirect; for implementation work, decompose into a Plan when it's more than one task (confirmed with the user), then hand off to dispatch |
| `dispatching-work` | skill | Choose `claude-p` vs. `herdr-pane` per task, write/track dispatch-instruction files under the user's home directory (`~/.straw-boss/dispatch/` — per-machine state, not project config), execute single dispatches or a whole Plan's wave-by-wave dispatch (`~/.straw-boss/plans/`), list outstanding dispatches, wrap one up |
| `init` | skill (user-invoked, one-time/occasional setup) | Ask which apps to manage, write `apps.json` and sync root `CLAUDE.md`; separately, record whether herdr-backed dispatch is enabled |
| `shipping-task` | skill (entry point) | Implementation lifecycle, user-picked per task: full flow (worktree → develop → MR → merge → archive) or light flow (direct commit to base) — delegated to the target app's own `gitWorkflowSkill` where configured, else this skill's fallback steps; dispatches via `dispatching-work` and gates every mutation on explicit user authorization |
| `inspecting-app` | skill (entry point) | Resolve app, hand off to your own `inspecting`-style skill — stays in-session, no dispatch |
| `investigating-app` | skill (entry point) | Resolve app, hand off to your own `investigating`-style skill — stays in-session, no dispatch |
| `troubleshooting-app` | skill (entry point) | Diagnose (app-code vs. infra) in-session, hand off to `shipping-task` once root cause is known |

`inspecting-app`/`investigating-app` hand off to general-purpose audit/research skills that aren't part of straw-boss — they're expected to already exist in your own Claude Code setup (most setups have something like this). If you don't have equivalents, those two entry points have nothing to hand off to; `shipping-task`, `troubleshooting-app`, and `work-on` stand on their own.

## Routing rule

1. One of the 4 entry-point skills (`shipping-task`, `inspecting-app`, `investigating-app`, `troubleshooting-app`) fires on the user's actual request.
2. That skill invokes `work-on` first: classify the request against the configured apps, applying any legacy redirect.
3. Read-only entry points (`inspecting-app`, `investigating-app`, `troubleshooting-app`'s diagnosis) continue directly in the current session against the resolved app's real files — no dispatch.
4. Implementation work (`shipping-task`, or `troubleshooting-app` handing off a fix) has every resolved app checked for an already-open, related OpenSpec change (`work-on` Task 4) before any task description is written — the user decides whether it's in scope. Requests resolving to more than one task then get confirmed as a Plan (`work-on` Task 5) before anything is dispatched; a single-task request skips straight to dispatch.
5. `shipping-task` assembles each task's description — pointing at an existing OpenSpec change by name where Task 4 found and confirmed one, never restating its scope — and invokes `dispatching-work` (single instruction, or the whole Plan), which picks a mode per task, writes instruction(s), and executes them in sessions rooted in the target app(s).
6. `shipping-task` obtains user authorization for every commit/push/merge each dispatched session reaches (reported as `awaiting-authorization`, not silence), resuming it to proceed rather than letting it self-authorize; it does the same for any tracker ticket tied to the work. A substantive work-content question (`awaiting-user-input`) is different — `shipping-task` only points the user at the task's own pane, it does not relay or resume.
7. `dispatching-work`'s wrap-up (single task) or auto-detach (Plan, on each task reaching `done`/`failed`) closes a finished instruction and any herdr pane/tab it used; for a full-flow task, worktree removal is the orchestrator's job too, paired with its orchestrator-created worktree.

## Why the app list is project config, not plugin code

Everything that used to be hardcoded per app (the routing table, legacy redirects, forbid-direct-commit rules, per-app git-workflow skills, gitignored local files a worktree needs, cross-app coordination pointers) is real knowledge about *your* project, not about straw-boss. `init` asks for it once and writes it to `.claude/straw-boss/apps.json` (schema: `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md`) plus a synced section in your project's root `CLAUDE.md`. The plugin ships with no apps configured — every routing decision comes from your project's own config, never a default guess.

## State: project config vs. machine state

- **`.claude/straw-boss/apps.json`** — project-level, checked into git, shared with the team. Which apps exist, how to route to them, their per-app quirks.
- **`~/.straw-boss/capability.json`, `~/.straw-boss/dispatch/`, `~/.straw-boss/plans/`** — per-user, per-machine operational state, outside any git checkout. Which dispatch mode this user prefers, what's currently dispatched, in-flight plans.

## External mutations stay gated

Commit/push/merge require explicit user authorization. A dispatched session cannot self-authorize one — `shipping-task`'s dispatch instructions explicitly tell the dispatched session to stop and report readiness rather than execute, and `shipping-task` (interactive with the actual user) obtains authorization and resumes it. This holds for both dispatch modes. Tracker-ticket mutations follow the same rule: a dispatched session never touches a ticket, only the orchestrating session does, once a whole plan (not just one task) is actually complete.

See `skills/dispatching-work/references/` for the exact mechanics (dispatch, plan, cross-session coordination) — this document covers the *why*, those cover the *how*.
