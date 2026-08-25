# Dispatch mechanics

Operational state lives under `Path.home() / ".straw-boss"`; target project
files are never modified to inject a dispatch workflow.

## Resolve mode and agent kind

- `capability.json` explicitly says `claude-p-only`: use headless mode.
- Otherwise use `herdr-pane` when `HERDR_ENV=1`; use headless only when no live
  herdr session exists.
- Resolve `agent_kind` independently: explicit per-dispatch override, then the
  app's `apps.json.agentKind`, then `claude`.

Resolve `<app_dir>` from the app configuration; never assume `apps/<app>`.

## Write the instruction and contract

Before launching anything, call:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/dispatch-task.py" write \
  --app <app> --slug <slug> --task "<task>" \
  --mode claude-p|herdr-pane --repo-root <repo_root> \
  [--batch <batch>] [--plan <plan> --task-id <task>] \
  --agent-kind claude|codex --main-agent-kind claude|codex \
  [--agent-model <model>] [--agent-effort <effort>] \
  [--main-agent-pane-id <pane> --main-agent-session-id <session>]
```

For `herdr-pane`, obtain both main-agent values from the current live herdr
record. The command creates:

- `<app>--<slug>.json`: pending instruction and receiver fingerprints;
- `<app>--<slug>.contract.md`: mandatory workflow text;
- a SHA-256 contract digest recorded in the instruction.

The contract contains the exact instruction-keyed progress, question, and
status commands. The task prompt carries work semantics, not a hand-copied
workflow.

## Permission mapping

Mirror the main agent's restriction tier; the dispatched agent must never be
more permissive.

| Tier | Claude | Codex interactive | Codex headless |
|---|---|---|---|
| unrestricted | `--dangerously-skip-permissions` | `--dangerously-bypass-approvals-and-sandbox` | same |
| guarded-write | default/`auto`/`acceptEdits`/`dontAsk` | `--sandbox workspace-write --ask-for-approval on-request` | `--sandbox workspace-write` |
| read-only | `plan`/`manual` | `--sandbox read-only` | `--sandbox read-only` |

Detect explicit Claude mode from `ps -p "$CLAUDE_PID" -ww -o args=`. Preserve
each flag as one argument; do not depend on shell word splitting.

## Interactive herdr launch

Create or reuse a tab, split a pane with cwd set to `<app_dir>`, and validate a
unique operator-visible agent name. Then run only:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/launch-dispatched-agent.py" \
  --instruction-path <instruction path> \
  --name <agent name> --pane-id <new pane> --tab-id <tab> \
  [--agent-arg <one provider argument>]...
```

The launcher:

1. verifies the instruction is pending and the contract digest matches;
2. injects Claude with `--append-system-prompt-file`, or Codex with
   `developer_instructions`;
3. starts the provider through herdr and handles an initial trust prompt;
4. submits the recorded task;
5. reads `agent_session.value`, cross-checking Claude's preassigned id;
6. writes `<app>--<slug>.launch.json`.

Confirm only after the launcher returns:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/dispatch-task.py" confirm \
  --app <app> --slug <slug>
```

Confirmation consumes the receipt and refuses any instruction, contract,
provider, pane, or session mismatch. It records the receipt values and moves
the instruction to `in-progress`.

## Headless launch

Headless mode has no live receiver. Inject the generated contract in the same
invocation that starts the process:

```bash
claude -p --session-id <instruction session_id> \
  --append-system-prompt-file <contract path> <permission flags> "<task>"
```

or:

```bash
codex exec --json <permission flags> \
  -c developer_instructions="$(<contract path>)" \
  [-m <model>] [-c model_reasoning_effort=<effort>] "<task>"
```

The process must write status through `report-task-status.py
--instruction-path` before exit. With no live main-agent endpoint, durable
status plus process/watcher observation is the recovery path. A Codex
continuation uses its recorded thread id with `codex exec resume` and includes
the same contract content again.

## Reporting and communication

- Progress: `report-progress.py --instruction-path ... --note ...`
- Checkpoint/outcome: `report-task-status.py --instruction-path ... --status ...`
- Generic question/FYI: `send-dispatch-message.py --instruction-path ...`
- Checkpoint reply: `reply-to-worker.py --worker-instruction-path ...`

Only these public scripts send cross-session messages. They resolve endpoints
from the instruction and validate live session fingerprints. The Plan watcher
observes durable content revisions and remains scheduling authority.

## Closing an instruction

Close only panes/tabs created for the dispatch. Then call `wrap-up-task.py`; it
archives the instruction and its contract, receipt, status, progress, and
delivery artifacts, and synchronizes terminal Plan status. Never archive a
non-terminal checkpoint or a task with a same-task continuation pending.
