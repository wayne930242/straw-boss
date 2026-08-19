# straw-boss

English | [繁體中文](./README.zh-TW.md)

Hand any piece of work — implementation, audit, research, or diagnosis — to a boss that decides how it gets done: a plain subagent for what doesn't need your app's own setup, or a session that actually lives in your app's directory — headless `claude -p`, or a watchable, joinable [herdr](https://github.com/herdrdev/herdr) pane — for what does. Code commits freely; every push and merge gets an authorization gate. Works in a single-app repo out of the box; routes across a monorepo's apps too.

Named after the ranch foreman who works the ground alongside the crew, not from an office. Same job here: get each task into the right hands, in the right place, and stay close enough to unblock it.

## Why

An app's own `.claude/skills/` and `.claude/settings.json` hooks only load for a session whose working directory is that app's own root — a monorepo root, or any cwd a boss runs from, never sees them. straw-boss dispatches the work itself into a session that actually lives there, instead of hand-maintaining a summary of what the app's rules say — for a code change, an audit, a piece of research, or a diagnosis alike, whenever the work actually needs that harness. Routing across a monorepo's apps (`work-on`) is a bonus on top, not a prerequisite. Full design rationale: `docs/architecture.md`.

## Workflow highlights

- **One door: `boss-say`** — hand over any work, whatever its size or shape; the boss triages scale and picks the execution tier itself. You never pick an entry skill.
- **Two tiers, judged per item** — a plain subagent for something that doesn't need your app's own setup, a dispatched agent rooted in the app for something that does.
- **One epic, one boss** — a single orchestrating session coordinates the whole epic; it delegates, never implements.
- **Per-task context** — each dispatch gets its own, scoped to one task, not the whole project.
- **Worktree isolation** — parallel tasks run side by side without colliding.
- **Cross-boss resource lock** — a file-based lock for ports and shared-DB migrations that worktrees can't isolate, across independent boss sessions.
- **Self-paced batches** — for a backlog too big for one turn, `boss-say` starts a `/loop` itself and refills its own dispatch slots.
- **herdr for human-in-the-loop** — watch a dispatch, join it, or answer a question mid-task; it's the default transport whenever it's available.

## Requirements

- Claude Code, with plugins enabled.
- [herdr](https://github.com/herdrdev/herdr) (recommended, optional). Without it, a dispatched agent runs headless `claude -p` — no live pane, no mid-task questions. With it, dispatch always uses a watchable, joinable pane. `init` checks for it and lets you enable or skip it.

## Install

```
/plugin marketplace add https://github.com/wayne930242/straw-boss
/plugin install straw-boss@straw-boss
```

Then run once per project:

```
/straw-boss:init
```

`init` asks which apps to manage (scanning for a common monorepo layout as a starting point), writes `.claude/straw-boss/apps.json`, syncs a managed-apps section into your project's root `CLAUDE.md`, offers a lightweight agent-system bootstrap for any app that has neither `CLAUDE.md` nor `.claude/`, and asks separately whether to enable herdr on this machine.

For a single-app repo, `init` is a convenience, not a precondition — `boss-say` works the moment the plugin is installed, resolving the repo root itself as the one implicit app. Run `init` when you want herdr enabled, `apps.json`'s per-app options (`forbidDirectCommit`, `localFiles`, ...), or a monorepo's multiple apps configured; skip it to just start handing over work.

## Skills

| Skill | Description |
|-------|-------------|
| `init` | One-time setup: ask which apps to manage, write the config, sync root `CLAUDE.md`, offer to bootstrap a missing agent system per app; decide whether to enable herdr dispatch |
| `boss-say` | **The entry point for everything.** Triages scale and, per item, the execution tier — a plain subagent, or a dispatched agent — then hands off to the matching specialist skill or its own capped-batch mechanics |
| `work-on` | Resolve a request to one of the configured apps, apply any legacy redirect |
| `dispatching-work` | Internal dispatch machinery, driven by `boss-say`'s specialists — picks the transport (`herdr-pane` whenever available, `claude-p` as the fallback), writes the dispatch instruction, actually dispatches, lists/wraps up existing dispatches |
| `shipping-task` | Decide the git lifecycle (worktree → develop → MR → merge → archive, or a direct commit), dispatch one task, commit freely, and get user authorization before every push/merge — driven by `boss-say` |
| `peeking-work` | Read-only peek at one dispatch's live progress — herdr pane output, or a `claude-p` transcript tail — without joining or interrupting it |
| `notifying-boss` | Used automatically by a dispatched agent to reach the boss with a purely informational report or question — herdr first, `SendMessage` as fallback |
| `create-great-harness` | Lightweight agent-system bootstrap for an app with neither `CLAUDE.md` nor `.claude/` — a short `CLAUDE.md` plus one pipe-tested guard hook |
| `inspecting-app` | Resolve the app, then run your own rules/conventions audit skill — solo or dispatched, per `boss-say`'s tier call — driven by `boss-say` |
| `investigating-app` | Resolve the app, then run your own research skill — solo or dispatched, same tier call — driven by `boss-say` |
| `troubleshooting-app` | Diagnose a reported failure — app-code vs. infrastructure, solo or dispatched — then hand the fix back to `boss-say` |

## Usage

Once `init` has run, hand any work to the boss — implementation, an audit, some research, a diagnosis, one item or a whole backlog:

```
boss-say fix the login redirect
boss-say audit the payments module against our rules
boss-say work through docs/backlog.md
```

`boss-say` decides the rest: it picks the execution tier per item — solo, or dispatched into the app — and the scale shape — one item through its matching specialist skill, several independent items as a capped batch, or a batch too big for one turn under a `/loop` it starts itself. You don't pick either — it states what it picked, and you override it in one sentence if you disagree.

Every specialist skill above is also directly invocable by name, if you'd rather trigger one yourself:

- Just want to know which app a request belongs to → `work-on`
- Check on an agent before joining or interrupting it → `peeking-work`
- Bootstrap a minimal agent system for an app that has none → `create-great-harness` (also offered automatically by `init`)
- Audit existing code against your rules → `inspecting-app`
- Research current behavior, no rule or failure in question → `investigating-app`
- Something's broken, cause unknown → `troubleshooting-app` (diagnoses, then hands the fix back to `boss-say`)

A status question or a close-out for a specific dispatch also goes through `boss-say`, which reads straight from `dispatching-work`'s own tracking.

## Configuration

Everything project-specific — apps, routing, per-app git-lifecycle quirks, legacy redirects, cross-app coordination — lives in `.claude/straw-boss/apps.json`, written by `init`. Schema: [skills/init/references/apps-config-schema.md](skills/init/references/apps-config-schema.md). `init` also keeps a terse managed-apps summary (names and directories only) synced into your project's root `CLAUDE.md`, since a monorepo root `CLAUDE.md` is inherited by every nested app session, not just straw-boss's own.

## License

[MIT](./LICENSE)
