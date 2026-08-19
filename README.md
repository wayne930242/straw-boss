# straw-boss

English | [繁體中文](./README.zh-TW.md)

You call the shots. Say the word, and `boss-say` dispatches it — to whoever's the right fit: a plain subagent for something simple, or a session rooted in the app's own directory (headless `claude -p`, or a watchable, joinable [herdr](https://github.com/herdrdev/herdr) pane) for anything that needs the app's own setup. Works in one app out of the box, coordinates across a whole monorepo too. You can always see what's actually happening.

Named after the ranch foreman who works the ground alongside the crew, not from an office.

## Why

An app's own `.claude/skills/` and `.claude/settings.json` hooks only load for a session actually rooted in that app's directory. straw-boss dispatches the work into a session that lives there, instead of hand-maintaining a summary of what the app's rules say — for a code change, an audit, research, or a diagnosis alike. Routing across a monorepo's apps (`work-on`) is a bonus, not a requirement. Full rationale: `docs/architecture.md`.

## Highlights

- **One door: `boss-say`** — hand over the work; it decides the scale and how to dispatch. You never pick an entry skill.
- **Two tiers** — a subagent when the app's own setup isn't needed, a dispatched agent when it is, judged per item.
- **One epic, one main agent** — a single session coordinates the whole epic; it delegates, never implements.
- **Worktree isolation** — parallel tasks run side by side.
- **Cross-main-agent resource lock** — a file lock for ports and shared-DB migrations worktrees can't isolate.
- **Self-paced batches** — a backlog too big for one turn gets its own `/loop`, started by `boss-say` itself.
- **herdr for human-in-the-loop** — watch it, join it, answer a question mid-task; the default whenever it's available.

## Requirements

- Claude Code, with plugins enabled.
- [herdr](https://github.com/herdrdev/herdr) (recommended, optional). Without it, dispatch runs headless `claude -p` — no live view, no mid-task questions. `init` asks whether to enable it.

## Install

```
/plugin marketplace add https://github.com/wayne930242/straw-boss
/plugin install straw-boss@straw-boss
```

Run once per project:

```
/straw-boss:init
```

`init` asks which apps to manage, writes `.claude/straw-boss/apps.json`, syncs your root `CLAUDE.md`, offers to bootstrap a missing agent system per app, and asks whether to enable herdr.

For a single app, `init` is a bonus — `boss-say` works the moment the plugin's installed. Run it when you want herdr, per-app options like `forbidDirectCommit`/`localFiles`, or a monorepo's apps configured.

## Skills

| Skill | Description |
|-------|-------------|
| `init` | Ask which apps to manage, write the config, sync root `CLAUDE.md`, offer to bootstrap a missing agent system per app, decide whether to enable herdr |
| `boss-say` | **The entry point for everything.** Judges scale, judges solo-vs-dispatch per item, hands off to the matching specialist skill or its own batch mechanics |
| `work-on` | Resolve a request to an app, apply any legacy redirect |
| `dispatching-work` | Internal dispatch machinery — picks the transport (`herdr-pane` when available, `claude-p` as the fallback), writes the instruction, dispatches, lists/wraps up existing dispatches |
| `shipping-task` | Decide the git lifecycle (worktree → develop → MR → merge → archive, or a direct commit), dispatch, commit freely, get authorization before every push/merge |
| `peeking-work` | Read-only peek at what a dispatch is currently doing, without joining or interrupting |
| `notifying-main-agent` | Used by a dispatched agent to reach the main agent with a purely informational report or question |
| `create-great-harness` | Bootstrap a minimal agent system for an app that has none — a short `CLAUDE.md` plus one guard hook |
| `inspecting-app` | Resolve the app, run your own rules-audit skill — solo or dispatched |
| `investigating-app` | Resolve the app, run your own research skill — solo or dispatched |
| `troubleshooting-app` | Diagnose a failure — app code or infrastructure, solo or dispatched — then hand the fix back to `boss-say` |

## Usage

Once `init`'s run, hand everything to the main agent:

```
boss-say fix the login redirect
boss-say audit the payments module against our rules
boss-say work through docs/backlog.md
```

`boss-say` decides the rest — solo or dispatched, one task or a batch, `/loop` or not. It states what it picked; you override in one sentence if you disagree.

Every specialist skill is also callable by name:

- Which app owns this? → `work-on`
- Peek before joining or interrupting → `peeking-work`
- No agent system for an app yet → `create-great-harness`
- Audit existing code → `inspecting-app`
- Research how something works now → `investigating-app`
- Something broke, cause unknown → `troubleshooting-app`

A status question or closing out a dispatch also goes through `boss-say`.

## Configuration

Everything project-specific lives in `.claude/straw-boss/apps.json`, written by `init`. Schema: [skills/init/references/apps-config-schema.md](skills/init/references/apps-config-schema.md). A terse summary also syncs into your root `CLAUDE.md`, since every nested app session inherits it.

## License

[MIT](./LICENSE)
