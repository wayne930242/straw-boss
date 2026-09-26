# straw-boss

English | [繁體中文](./README.zh-TW.md)

You call the shots. Give `boss-say` one task or a backlog and it chooses the smallest sufficient loop: carry bounded work here, fan out clear branches, or coordinate app-rooted Claude Code, Codex CLI, and Antigravity workrooms when separate ownership or continuity is useful. It works in a single app out of the box and coordinates across a monorepo when needed.

Named after the ranch foreman who works the ground alongside the crew, not from an office.

## Why

Bounded work should stay bounded. When a task benefits from its own workroom, straw-boss roots that worker in the app it owns instead of copying the app's context into a summary that can drift. Claude Code workers load that app's `.claude/skills/` and `.claude/settings.json` hooks there; Claude Code, Codex CLI, and Antigravity workers all operate from the correct app directory and local instructions. The same routing applies to implementation, audits, research, and diagnosis. Cross-app routing through `resolving-app` is available for monorepos, not required for a single app. Full rationale: [docs/architecture.md](docs/architecture.md).

## Highlights

- **One door: `boss-say`** — hand over the work; it selects the owner, execution tier, coordination graph, and reality anchor.
- **Smallest sufficient loop** — bounded work stays with the current agent; clear branches fan out; durable app-rooted work gets its own workroom.
- **Claude Code, Codex CLI, and Antigravity workers** — choose provider, profile, model, and effort per work route; Claude routes can also use a native advisor.
- **Event-driven coordination** — persisted checkpoints and terminal status drive scheduling, handoffs, and cleanup.
- **Worktree isolation** — team-mode tasks can run side by side on their own feature branches.
- **Cross-main-agent resource lock** — a file lock for ports and shared-DB migrations worktrees can't isolate.
- **Self-paced batches** — a backlog too big for one turn gets its own `/loop`, started by `boss-say` itself.
- **Independent orchestrator handoff** — with your approval, move one scope and its in-progress dispatches into a named Herdr tab whose orchestrator takes over through `boss-say`; the original window leaves that scope.
- **herdr for human-in-the-loop** — watch or join a dispatched Claude Code, Codex CLI, or Antigravity workroom and answer questions there.

## Requirements

- Claude Code with plugins enabled, Codex CLI with plugin support, Google Antigravity (AGY CLI), or Pi with [`pi-herdr-agents`](https://github.com/giuseppecrj/pi-herdr-agents).
- Python 3 for the bundled lifecycle and installation scripts.
- [Herdr](https://github.com/herdrdev/herdr), required for dispatch. Claude Code, Codex CLI, and Antigravity workers all run in a Herdr pane you can watch and join. Installing, reading configuration, and tidying persisted state all work on their own; starting a dispatch needs a running Herdr service and a current pane.

## Install

From a source checkout, install or update every supported CLI available on this
machine from the GitHub marketplace source and verify the installed version:

```bash
bash scripts/install.sh
```

For development against this checkout instead, opt into its machine-local path
explicitly:

```bash
bash scripts/install.sh --local
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

### Antigravity (AGY CLI)

```bash
agy plugin install wayne930242/straw-boss
```

Then run once per project:

```text
/straw-boss:init
```

`init` confirms the managed apps and work routes, writes `.straw-boss/apps.json`, syncs the root `AGENTS.md` and `CLAUDE.md`, offers to fill in each app's missing instruction files, and checks the Herdr dispatch requirement.

### Pi

```bash
pi install git:github.com/wayne930242/straw-boss
```

Pi loads `boss-say`, `resolving-app`, `choosing-graph`, `shipping-task`, `reporting-to-user`, and `dispatching-work`, plus the `dispatch_control` extension. A Pi main agent keeps the same workflow and dispatches Pi workers through `pi-herdr-agents`; it runs none of the bundled Python scripts. Worker models come from the tiers of your Pi model strategy. Its skills are a separate Pi set under `pi/skills/`, so the Claude Code, Codex, and Antigravity skills stay as they are. See [Pi dispatching-work](pi/skills/dispatching-work/SKILL.md).

For a single app, `init` is a bonus — `boss-say` works the moment the plugin's installed. Run it to check Herdr readiness, configure per-app options like `forbidDirectCommit`/`localFiles`, or a monorepo's apps configured.

## Usage

Once `init`'s run, hand everything to the main agent:

```
boss-say fix the login redirect
boss-say audit the payments module against our rules
boss-say work through docs/backlog.md
```

`boss-say` decides the rest: the owning skill, whether the current agent can
carry the work or a separate workroom is useful, the coordination graph and
reality anchor, one task or a batch, and `/loop` when a backlog needs its own
pacing. It states what it picked, and you can override it in one sentence.

## Skills

Call a skill by name when the situation fits; anything unlisted goes to `boss-say`.

| When you want to… | Use |
|-------|-------------|
| Fix, build, audit, research, or diagnose; work through a backlog; ask what is running; close out a dispatch | `boss-say` |
| Set up managed apps and work routes, or check Herdr readiness | `init` |
| Find which app owns a request | `resolving-app` |
| See what a dispatch is doing without joining or interrupting it | `peeking-work` |
| Move a scope and its in-progress dispatches to a new orchestrator tab | `handoff-orchestrator` |
| Have this window take over dispatches another main agent coordinates | `boss-say`; it moves them only when you ask |
| Resolve friction in Straw Boss's own coordination | `boss-assistant` |
| Give an app without `AGENTS.md` or `CLAUDE.md` a minimal agent system | `create-great-harness` |
| From inside a dispatched worker, bring in a coworker for review or pairing | `bringing-coworker` |

The main agent and workers run the other skills on their own: `i-am-orchestrator`, `choosing-graph`, `dispatching-work`, `shipping-task`, `contacting-orchestrators`, `reporting-to-user`, `notifying-main-agent`, `asking-peer-agents`, and `agent-feedback`.
[docs/architecture.md](docs/architecture.md#components) describes each one.

## Configuration

`init` writes the managed apps and each app's lifecycle configuration to `.straw-boss/apps.json`. The format is the [apps config schema](skills/init/references/apps-config-schema.md). The app summary and the project's work routes are synced into the root `AGENTS.md` and `CLAUDE.md`.

An app's `agentKind` names its default agent. The project's work routes name the provider profile, model, effort, and an optional Claude advisor, which `init` syncs into both instruction files; a Codex route records `advisor: none`.

Configuration is read from `.straw-boss/apps.json` first, falling back to `.claude/straw-boss/apps.json` when the new path does not exist. `init` writes the confirmed old configuration to the new path, leaves the old file in place, and reports that it has been superseded.

## License

[MIT](./LICENSE)

## Experimental Jev pruning

Jev pruning is opt-in and leaves ordinary context renewal unchanged. Enable it
for one newly launched Claude session (with `TYPESAFE_API_KEY` in the environment):

```sh
STRAW_BOSS_JEV=1 CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude
```

Start a session with the experiment explicitly off:

```sh
STRAW_BOSS_JEV=0 claude
```

Restart or resume with the desired switch; keep pruning off globally during the
renewal acceptance window through 2026-09-25. See
[benchmark, recovery, and implementation limits](docs/jev-pruning.md).

For Codex in Herdr, use `STRAW_BOSS_JEV=1 codex` with the same nonblank key.
At the 200k renewal point, Jev attempts a pruned `codex resume` in the same pane;
gate misses and failures use ordinary continuity renewal. See the
[Codex renewal behavior and accounting costs](docs/jev-codex-renewal.md).
