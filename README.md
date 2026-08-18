# straw-boss

English | [繁體中文](./README.zh-TW.md)

Dispatch implementation work into a session that actually lives in your app's directory — headless `claude -p`, or a watchable, joinable [herdr](https://github.com/herdrdev/herdr) pane — with a standardized git lifecycle and an authorization gate on every commit/push/merge. Works in a single-app repo out of the box; routes across a monorepo's apps too.

Named after the ranch foreman who works the ground alongside the crew, not from an office. Same job here: get each task into the right hands, in the right place, and stay close enough to unblock it.

## Why

An app's own `.claude/skills/` and `.claude/settings.json` hooks only load for a session whose working directory is that app's own root — a monorepo root, or any cwd a boss runs from, never sees them. straw-boss dispatches the work itself into a session that actually lives there, instead of hand-maintaining a summary of what the app's rules say. Routing across a monorepo's apps (`work-on`) is a bonus on top, not a prerequisite. Full design rationale: `docs/architecture.md`.

## Workflow highlights

- **One epic, one boss** — a single orchestrating session coordinates the whole epic; it delegates, never implements.
- **Per-task context** — each dispatch gets its own, scoped to one task, not the whole project.
- **Worktree isolation** — parallel tasks run side by side without colliding.
- **`/loop` for batches** — `boss-say` self-paces a batch of tasks across turns.
- **herdr for human-in-the-loop** — watch a dispatch, join it, or answer a question mid-task.

## Requirements

- Claude Code, with plugins enabled.
- [herdr](https://github.com/herdrdev/herdr) (recommended, optional). Without it, dispatch runs headless `claude -p` — no live pane, no mid-task questions. With it, you get a watchable, joinable pane. `init` checks for it and lets you enable or skip it.

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

## Skills

| Skill | Description |
|-------|-------------|
| `init` | One-time setup: ask which apps to manage, write the config, sync root `CLAUDE.md`, offer to bootstrap a missing agent system per app; decide whether to enable herdr dispatch |
| `work-on` | Resolve a request to one of the configured apps, apply any legacy redirect; hand implementation requests to dispatch |
| `dispatching-work` | Choose the dispatch mode (`claude-p` / `herdr-pane`), write the dispatch instruction, actually dispatch, list/wrap up existing dispatches |
| `shipping-task` | Decide the git lifecycle (worktree → develop → MR → merge → archive, or a direct commit), dispatch one task, and get user authorization before every commit/push/merge |
| `boss-say` | Drive a batch of independent tasks under a concurrency cap, refilling as items finish; runs as one long turn or repeatedly via `/loop` |
| `peeking-work` | Read-only peek at one dispatch's live progress — herdr pane output, or a `claude-p` transcript tail — without joining or interrupting it |
| `notifying-boss` | Used automatically by a dispatched agent to reach the boss with a purely informational question — herdr first, `SendMessage` as fallback |
| `create-great-harness` | Lightweight agent-system bootstrap for an app with neither `CLAUDE.md` nor `.claude/` — a short `CLAUDE.md` plus one pipe-tested guard hook |
| `inspecting-app` | Resolve the app, hand off to your own rules/conventions audit skill (read-only, no dispatch) |
| `investigating-app` | Resolve the app, hand off to your own research skill (read-only, no dispatch) |
| `troubleshooting-app` | Diagnose a reported failure — app-code vs. infrastructure — then hand off to `shipping-task` for the fix |

## Usage

Once `init` has run, trigger whichever entry skill matches what you're doing:

- Start implementing something → `shipping-task` (calls `work-on`, then dispatches)
- Work through a batch of independent tasks → `boss-say` (one turn, or `/loop boss-say ...` to self-pace across many)
- Just want to know which app a request belongs to → `work-on`
- Check on an agent before joining or interrupting it → `peeking-work`
- Audit existing code against your rules → `inspecting-app`
- Research current behavior, no rule or failure in question → `investigating-app`
- Something's broken, cause unknown → `troubleshooting-app`
- See what's currently dispatched, or close one out → `dispatching-work`

## Configuration

Everything project-specific — apps, routing, per-app git-lifecycle quirks, legacy redirects, cross-app coordination — lives in `.claude/straw-boss/apps.json`, written by `init`. Schema: [skills/init/references/apps-config-schema.md](skills/init/references/apps-config-schema.md). `init` also keeps a terse managed-apps summary (names and directories only) synced into your project's root `CLAUDE.md`, since a monorepo root `CLAUDE.md` is inherited by every nested app session, not just straw-boss's own.

## License

[MIT](./LICENSE)
