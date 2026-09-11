# straw-boss

English | [繁體中文](./README.zh-TW.md)

You call the shots. Give `boss-say` one task or a backlog and it chooses the smallest sufficient loop: carry bounded work here, fan out clear branches, or coordinate app-rooted Claude Code and Codex CLI workrooms when separate ownership or continuity is useful. It works in a single app out of the box and coordinates across a monorepo when needed.

Named after the ranch foreman who works the ground alongside the crew, not from an office.

## Why

Bounded work should stay bounded. When a task benefits from its own workroom, straw-boss roots that worker in the app it owns instead of copying the app's context into a summary that can drift. Claude Code workers load that app's `.claude/skills/` and `.claude/settings.json` hooks there; Claude Code and Codex CLI workers both operate from the correct app directory and local instructions. The same routing applies to implementation, audits, research, and diagnosis. Cross-app routing through `work-on` is available for monorepos, not required for a single app. Full rationale: [docs/architecture.md](docs/architecture.md).

## Highlights

- **One door: `boss-say`** — hand over the work; it selects the owner, execution tier, coordination graph, and reality anchor.
- **Smallest sufficient loop** — bounded work stays with the current agent; clear branches fan out; durable app-rooted work gets its own workroom.
- **Claude Code and Codex CLI workers** — choose provider, profile, model, and effort per work route; Claude routes can also use a native advisor.
- **Event-driven coordination** — persisted checkpoints and terminal status drive scheduling, handoffs, and cleanup.
- **Worktree isolation** — team-mode tasks can run side by side on their own feature branches.
- **Cross-main-agent resource lock** — a file lock for ports and shared-DB migrations worktrees can't isolate.
- **Self-paced batches** — a backlog too big for one turn gets its own `/loop`, started by `boss-say` itself.
- **Independent orchestrator handoff** — with your approval, move one scope into a named Herdr tab whose orchestrator takes over through `boss-say`; the original window leaves that scope.
- **herdr for human-in-the-loop** — watch or join a dispatched Claude Code or Codex CLI workroom and answer questions there.

## Requirements

- Claude Code with plugins enabled, or Codex CLI with plugin support.
- Python 3 for the bundled lifecycle and installation scripts.
- [Herdr](https://github.com/herdrdev/herdr), required for dispatch. Claude Code and Codex CLI workers both run in a Herdr pane you can watch and join. Installing, reading configuration, and tidying persisted state all work on their own; starting a dispatch needs a running Herdr service and a current pane.

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

`init` confirms the managed apps and work routes, writes `.straw-boss/apps.json`, syncs the root `AGENTS.md` and `CLAUDE.md`, offers to fill in each app's missing instruction files, and checks the Herdr dispatch requirement.

For a single app, `init` is a bonus — `boss-say` works the moment the plugin's installed. Run it to check Herdr readiness, configure per-app options like `forbidDirectCommit`/`localFiles`, or a monorepo's apps configured.

## Skills

| Skill | Description |
|-------|-------------|
| `init` | Configure managed apps, work routes, and Herdr dispatch; sync the root `AGENTS.md` and `CLAUDE.md`, and offer to fill in each app's instruction files |
| `boss-say` | **The entry point.** Resolves the owner and execution tier, and plans/schedules independent or dependent tasks |
| `handoff-orchestrator` | After explicit approval, transfer one scope and its minimal continuity state to a new orchestrator tab |
| `boss-assistant` | Resolve coordination friction, verify recovery with the reporting main agent, and carry source findings into the development workflow |
| `contacting-orchestrators` | Register this orchestrator's identity and one-line scope, read which other orchestrators are live, and send one a factual delta carrying this session's herdr pane id |
| `i-am-orchestrator` | Keep coordination event-driven while workers and the user own work details inside the named reality anchor |
| `work-on` | Resolve a request to an app, apply any legacy redirect |
| `dispatching-work` | Internal dispatch machinery — picks the transport and resolves a work route (provider/profile/model/effort, plus Claude-only native advisor), writes the instruction, dispatches, lists/wraps up existing dispatches |
| `choosing-graph` | Pick the coordination graph (single-loop, sub-agent fan-out/fan-in, orchestrator-worker) and the reality anchor (testing, pseudo-human, human, adversarial review) before work starts — the anchor names the category, the agent doing the work still picks the method inside it |
| `shipping-task` | Decide the git lifecycle from how you regard the work — team-mode (worktree → develop → MR → merge → archive) or solo-mode (direct commit) — dispatch, commit and push its own feature branch freely, get authorization before every merge (and any push outside that branch) |
| `peeking-work` | Read-only peek at what a dispatch is currently doing, without joining or interrupting |
| `reporting-to-user` | Close out finished work: grade what surfaced as Alert (act now), Warn (carry knowingly), or Info (informational), then ask whether each Alert and Warn finding gets a follow-up dispatch |
| `notifying-main-agent` | Used by a dispatched agent to reach the main agent with a purely informational report or question |
| `asking-peer-agents` | Let one dispatched task request a factual progress update or conclusion from another task |
| `bringing-coworker` | Bring one Claude Code or Codex CLI coworker into an interactive worker's exact Herdr tab and worktree |
| `create-great-harness` | Write or complete `AGENTS.md` and `CLAUDE.md` from project evidence, adding an optional hook or rule within the confirmed scope |

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

Every specialist skill is also callable by name:

- Which app owns this? → `work-on`
- Peek before joining or interrupting → `peeking-work`
- No agent system for an app yet → `create-great-harness`
- Audit existing code, or research how something works now → `boss-say` (dispatched on the question alone; the worker picks its own method)
- Something broke, cause unknown → `boss-say` (diagnosis and repair stay in one `shipping-task` loop)

A status question or closing out a dispatch also goes through `boss-say`.

## Configuration

`init` writes the managed apps and each app's lifecycle configuration to `.straw-boss/apps.json`. The format is the [apps config schema](skills/init/references/apps-config-schema.md). The app summary and the project's work routes are synced into the root `AGENTS.md` and `CLAUDE.md`.

An app's `agentKind` names its default agent. The project's work routes name the provider profile, model, effort, and an optional Claude advisor, which `init` syncs into both instruction files; a Codex route records `advisor: none`.

Configuration is read from `.straw-boss/apps.json` first, falling back to `.claude/straw-boss/apps.json` when the new path does not exist. `init` writes the confirmed old configuration to the new path, leaves the old file in place, and reports that it has been superseded.

## License

[MIT](./LICENSE)
