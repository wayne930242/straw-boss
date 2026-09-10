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
- [herdr](https://github.com/herdrdev/herdr) (recommended, optional). With it, dispatched Claude Code and Codex CLI workrooms are visible and joinable. Without a live herdr session, separate workrooms run headlessly.

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

`init` 會確認 managed apps 與 work routes，寫入 `.straw-boss/apps.json`，同步根目錄的 `AGENTS.md` 與 `CLAUDE.md`，提議補齊各 app 缺少的指引檔，並記錄是否啟用 herdr dispatch。

For a single app, `init` is a bonus — `boss-say` works the moment the plugin's installed. Run it when you want herdr, per-app options like `forbidDirectCommit`/`localFiles`, or a monorepo's apps configured.

## Skills

| Skill | Description |
|-------|-------------|
| `init` | 設定 managed apps、work routes 與 herdr dispatch；同步根目錄的 `AGENTS.md`、`CLAUDE.md`，並提議補齊各 app 的指引檔 |
| `boss-say` | **The entry point for everything.** Selects the owning skill and smallest sufficient loop for one task, an independent batch, or a backlog |
| `handoff-orchestrator` | After explicit approval, transfer one scope and its minimal continuity state to a new orchestrator tab |
| `boss-assistant` | 老闆助理：將各協調者的摩擦當作 Straw Boss UAT，修復 graph 並依量測優化效能與儲存；先查本地專案，再準備 issue／PR 並詢問是否發布 |
| `contacting-orchestrators` | Register this orchestrator's identity and one-line scope, read which other orchestrators are live, and send one a factual delta carrying this session's herdr pane id |
| `i-am-orchestrator` | Keep coordination event-driven while workers and the user own work details inside the named reality anchor |
| `work-on` | Resolve a request to an app, apply any legacy redirect |
| `dispatching-work` | Internal dispatch machinery — picks the transport and resolves a work route (provider/profile/model/effort, plus Claude-only native advisor), writes the instruction, dispatches, lists/wraps up existing dispatches |
| `choosing-graph` | Pick the coordination graph (single-loop, sub-agent fan-out/fan-in, orchestrator-worker) and the reality anchor (testing, pseudo-human, human, adversarial review) before work starts — the anchor names the category, the agent doing the work still picks the method inside it |
| `shipping-task` | Decide the git lifecycle from how you regard the work — team-mode (worktree → develop → MR → merge → archive) or solo-mode (direct commit) — dispatch, commit and push its own feature branch freely, get authorization before every merge (and any push outside that branch) |
| `peeking-work` | Read-only peek at what a dispatch is currently doing, without joining or interrupting |
| `notifying-main-agent` | Used by a dispatched agent to reach the main agent with a purely informational report or question |
| `asking-peer-agents` | Let one dispatched task request a factual progress update or conclusion from another task |
| `bringing-coworker` | Bring one Claude Code or Codex CLI coworker into an interactive worker's exact Herdr tab and worktree |
| `create-great-harness` | 依專案證據建立或補齊 `AGENTS.md`、`CLAUDE.md`，依已確認範圍加入可選 hook／rule |
| `inspecting-app` | Resolve the app and run an evidence-bearing rules audit through the smallest sufficient loop |
| `investigating-app` | Resolve the app and explain its current behavior with evidence through the smallest sufficient loop |
| `troubleshooting-app` | Keep ordinary diagnosis and repair in one `shipping-task` loop; split out only an integration preflight whose evidence is needed to route or schedule later work |

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
- Audit existing code → `inspecting-app`
- Research how something works now → `investigating-app`
- Something broke, cause unknown → `troubleshooting-app`

A status question or closing out a dispatch also goes through `boss-say`.

## Configuration

`init` 將 managed apps 與各 app 的生命週期設定寫入 `.straw-boss/apps.json`。格式見 [apps config schema](skills/init/references/apps-config-schema.md)。app 摘要與專案 work routes 同步至根目錄的 `AGENTS.md` 與 `CLAUDE.md`。

app 的 `agentKind` 指定預設 agent。專案 work routes 則指定 provider profile、model、effort 與可選的 Claude advisor，由 `init` 同步至兩個指引檔；Codex route 的 advisor 為 none。

設定讀取優先使用 `.straw-boss/apps.json`；新路徑不存在時相容 `.claude/straw-boss/apps.json`。`init` 將確認後的舊設定寫入新路徑並保留舊檔，回報其已被取代。

## License

[MIT](./LICENSE)
