# straw-boss

English | [繁體中文](./README.zh-TW.md)

You call the shots. Say the word, and `boss-say` dispatches it — to whoever's the right fit: a plain subagent for something simple, or a session rooted in the app's own directory (headless, or a watchable, joinable [herdr](https://github.com/herdrdev/herdr) pane — `claude` by default, another agent CLI like `codex` where configured) for anything that needs the app's own setup. Works in one app out of the box, coordinates across a whole monorepo too. You can always see what's actually happening.

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

- Claude Code with plugins enabled, or Codex CLI with plugin support.
- [herdr](https://github.com/herdrdev/herdr) (recommended, optional). Without it, dispatch runs headless `claude -p` — no live view, no mid-task questions. `init` asks whether to enable it.

## Install

From a source checkout, install or update every supported CLI available on this
machine and verify the installed version:

```bash
bash scripts/install.sh
```

Restart active agent sessions afterward. The equivalent manual commands are
below.

### Claude Code

```
/plugin marketplace add https://github.com/wayne930242/straw-boss
/plugin install straw-boss@straw-boss
```

Then run once per project:

```
/straw-boss:init
```

### Codex CLI

```bash
codex plugin marketplace add wayne930242/straw-boss --ref main
codex plugin add straw-boss@straw-boss
```

Start a new Codex session so it loads the installed skills and hooks, review and trust the bundled hooks when prompted, then run once per project:

```text
$straw-boss:init
```

You can also browse or manage the installed plugin interactively by starting `codex` and entering `/plugins`. Plugins are not available in the Codex IDE extension.

`init` asks which apps to manage, writes `.claude/straw-boss/apps.json`, syncs your root `CLAUDE.md`, offers to bootstrap a missing agent system per app, and asks whether to enable herdr.

For a single app, `init` is a bonus — `boss-say` works the moment the plugin's installed. Run it when you want herdr, per-app options like `forbidDirectCommit`/`localFiles`, or a monorepo's apps configured.

## Skills

| Skill | Description |
|-------|-------------|
| `init` | Ask which apps to manage, write the config, sync root `CLAUDE.md`, configure work routes with provider profile/model/effort and an optional Claude advisor, offer to bootstrap a missing agent system per app, decide whether to enable herdr |
| `boss-say` | **The entry point for everything.** Judges scale, judges solo-vs-dispatch per item, hands off to the matching specialist skill or its own batch mechanics |
| `work-on` | Resolve a request to an app, apply any legacy redirect |
| `dispatching-work` | Internal dispatch machinery — picks the transport and resolves a work route (provider/profile/model/effort, plus Claude-only native advisor), writes the instruction, dispatches, lists/wraps up existing dispatches |
| `choosing-graph` | Pick the coordination graph (single-loop, sub-agent fan-out/fan-in, orchestrator-worker) and the reality anchor (testing, pseudo-human, human, adversarial review) before work starts |
| `shipping-task` | Decide the git lifecycle from how you regard the work — team-mode (worktree → develop → MR → merge → archive) or solo-mode (direct commit) — dispatch, commit and push its own feature branch freely, get authorization before every merge (and any push outside that branch) |
| `peeking-work` | Read-only peek at what a dispatch is currently doing, without joining or interrupting |
| `notifying-main-agent` | Used by a dispatched agent to reach the main agent with a purely informational report or question |
| `create-great-harness` | Bootstrap a minimal agent system for an app that has none — an evidence-grounded `CLAUDE.md`, plus optional hook or rule artifacts when confirmed scope or project evidence requires them |
| `inspecting-app` | Dispatch an evidence-bearing rules audit into the app; bounded audits may use a confirmed lower-tier route |
| `investigating-app` | Dispatch current-state research into the app and return an explanation with evidence, not a binary answer |
| `troubleshooting-app` | Keep ordinary diagnosis and repair in one `shipping-task` worker; split out only an integration preflight whose evidence is needed to route or schedule later dispatches |

## Usage

Once `init`'s run, hand everything to the main agent:

```
boss-say fix the login redirect
boss-say audit the payments module against our rules
boss-say work through docs/backlog.md
```

`boss-say` decides the rest — solo only when no managed-app files are needed,
otherwise dispatched; one task or a batch; `/loop` or not. It states what it
picked, and you can override it in one sentence.

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

An app can also default to a non-`claude` agent kind (`agentKind`). Complete work routes — provider profile, model, effort, and optional Claude Code native advisor — are a separate project-wide policy `init` writes into root `CLAUDE.md` as prose. Codex routes do not support advisor.

## License

[MIT](./LICENSE)
