# straw-boss

English | [繁體中文](./README.zh-TW.md)

A Claude Code plugin that dispatches implementation work into a session rooted in your app's own directory — a headless `claude -p` process, or an interactive [herdr](https://github.com/herdrdev/herdr) pane you can watch and join — with a standardized git lifecycle and an authorization gate on every commit/push/merge. Works directly in a single-app repo; in a monorepo, it also routes each request to the right app first.

The name is a ranch term: the straw boss is the crew foreman who works alongside the hands, not from an office. That's the job here — get each task into the right hands, in the right place, and stay close enough to unblock it.

## Why

An app's own `.claude/skills/` and `.claude/settings.json` hooks only load for a session whose working directory is that app's own root. A session working from somewhere else — a monorepo root, or any orchestrating cwd — never sees them, even though path-scoped rules and nested `CLAUDE.md` files do reach it. straw-boss closes that gap by dispatching the work itself into a session that actually lives in the target directory, instead of hand-maintaining a summary of what that app's rules say. This is the core of the plugin — routing across a monorepo's multiple apps (`work-on`) is an extra layer on top, not a precondition for the rest of it. See `docs/architecture.md` for the full design rationale.

## Requirements

- Claude Code, with plugins enabled.
- [herdr](https://github.com/herdrdev/herdr) (recommended, optional). Without it, every dispatch runs as a headless `claude -p` process — no live pane, no mid-task questions. With it, straw-boss can open an interactive pane you can watch, join, and get asked mid-task questions in. `init` checks for it and lets you enable it, or skip it and stay `claude-p`-only.

## Install

```
/plugin marketplace add https://github.com/wayne930242/straw-boss
/plugin install straw-boss@straw-boss
```

Then run `init` once per project:

```
/straw-boss:init
```

`init` asks which apps you want to manage (scanning for a common monorepo layout as a starting point), writes `.claude/straw-boss/apps.json`, and syncs a managed-apps section into your project's root `CLAUDE.md`. It also asks, separately, whether to enable herdr-backed dispatch on this machine.

## Skills

| Skill | Description |
|-------|-------------|
| `init` | One-time setup: ask which apps to manage, write the config, sync root `CLAUDE.md`; decide whether to enable herdr dispatch |
| `work-on` | Resolve a request to one of the configured apps, apply any legacy redirect; hand implementation requests to dispatch |
| `dispatching-work` | Choose the dispatch mode (`claude-p` / `herdr-pane`), write the dispatch instruction, actually dispatch, list/wrap up existing dispatches |
| `shipping-task` | Decide the git lifecycle (worktree → develop → MR → merge → archive, or a direct commit), dispatch one task, and get user authorization before every commit/push/merge |
| `boss-say` | Drive a batch of independent tasks under a concurrency cap, refilling as items finish; runs as one long turn or repeatedly via `/loop` |
| `inspecting-app` | Resolve the app, hand off to your own rules/conventions audit skill (read-only, no dispatch) |
| `investigating-app` | Resolve the app, hand off to your own research skill (read-only, no dispatch) |
| `troubleshooting-app` | Diagnose a reported failure — app-code vs. infrastructure — then hand off to `shipping-task` for the fix |

## Usage

Once `init` has run, trigger whichever entry skill matches what you're doing:

- Start implementing something → `shipping-task` (internally calls `work-on`, then dispatches)
- Work through a batch of independent tasks → `boss-say` (one turn, or `/loop boss-say ...` to self-pace across many turns)
- Just want to know which app a request belongs to → `work-on`
- Audit existing code against your rules → `inspecting-app`
- Research current behavior, no rule or failure in question → `investigating-app`
- Something's broken, cause unknown → `troubleshooting-app`
- See what's currently dispatched, or close one out → `dispatching-work`

## Configuration

Everything project-specific — which apps exist, how to route to them, per-app git-lifecycle quirks, legacy redirects, cross-app coordination pointers — lives in `.claude/straw-boss/apps.json`, written by `init`. Schema: [skills/init/references/apps-config-schema.md](skills/init/references/apps-config-schema.md). `init` also keeps a short managed-apps summary (names and directories only) synced into your project's root `CLAUDE.md` — kept deliberately terse, since a monorepo root `CLAUDE.md` is inherited by every nested app session, not just straw-boss's own.

## License

[MIT](./LICENSE)
