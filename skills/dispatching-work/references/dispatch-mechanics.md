# Dispatch mechanics

Operational state lives under `Path.home() / ".straw-boss"`.
[dispatching-work](../SKILL.md) owns the lifecycle; this reference supplies CLI contracts and recovery details.

## Resolve mode and work route

Dispatch uses `herdr-pane`.
Confirm the service and current pane's live record before writing an instruction.
Resolve a complete worker setup in this order:

1. Explicit per-dispatch override.
2. Matching root `AGENTS.md` work route; consult `CLAUDE.md` when no route section exists there.
3. The app's `apps.json.agentKind`.
4. Claude with provider defaults.

A setup includes provider, profile, model, effort, and Claude's optional native advisor.
Codex records no advisor; report an incompatible combination.
If both instruction files carry conflicting routes, resolve the user's choice for this dispatch; [init](../../init/SKILL.md#configure-work-routes) owns synchronization.

## Write the instruction and contract

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/dispatch-task.py" write \
  --app <app> --slug <slug> --task "<brief>" \
  --mode herdr-pane --repo-root <verified-cwd> \
  [--batch <batch>] [--plan <plan> --task-id <task>] [--role <workroom>] \
  --agent-kind claude|codex --main-agent-kind claude|codex \
  [--agent-profile <profile>] [--agent-model <model>] \
  [--agent-effort <effort>] [--advisor-model <claude-model>] \
  --main-agent-pane-id <pane> \
  [--main-agent-session-id <session>] [--main-agent-terminal-id <terminal>]
```

Supply the required provider fingerprint from [Record the main agent before launch](cross-session-coordination.md#record-the-main-agent-before-launch).
`--role` is an already-known workroom label such as `database` or `frontend`; it distinguishes tasks sharing an app.

The command creates a pending `<app>--<slug>.json`, immutable `.contract.md`, and recorded SHA-256 digest.
It generates identity and reporting mechanics.
The brief follows [Write the brief](../SKILL.md#write-the-brief).

## Permission mapping

Mirror the main agent's restriction tier within the current authorization; the dispatched agent must never be more permissive.

| Tier | Claude | Codex |
|---|---|---|
| unrestricted | `--dangerously-skip-permissions` | `--dangerously-bypass-approvals-and-sandbox` |
| guarded-write | default/`auto`/`acceptEdits`/`dontAsk` | `--sandbox workspace-write --ask-for-approval on-request` |
| read-only | `plan`/`manual` | `--sandbox read-only` |

Read the main provider's active configuration and process arguments; for Claude, use `ps -p "$CLAUDE_PID" -ww -o args=`.
Preserve each flag as one argument.
An uncertain restriction tier must be resolved before launch.

## Interactive herdr launch

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/launch-dispatched-agent.py" \
  --instruction-path <instruction-path> \
  [--name <agent-name>] [--agent-arg=<one-provider-argument>]...
```

Run in the foreground through completion.
The launcher derives a unique name from `role`, then `app`, and splits a pane in the recorded main pane's tab with the instruction's `repo_root` as cwd.
Omit `--name` for automatic collision handling; an explicit name is used as given.

Provider profile/model/effort and Claude advisor come from the instruction.
Use `--agent-arg=<value>` for additional provider options, with `=` so a leading dash remains the value.
Instruction-owned options are validated against duplication.

The launcher verifies the contract digest, injects the contract before the first turn, confirms task delivery through the provider transcript and Herdr lifecycle gate, writes `.launch.json`, and confirms the instruction as `in-progress`.
Inspect `confirmed: true` before reporting dispatch success.

For `confirmed: false`, keep the running worker and execute the confirmation repair named by the warning:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/dispatch-task.py" confirm \
  --app <app> --slug <slug>
```

The receipt and live identity must match.
Already-confirmed instructions return `already_confirmed`.
Claude's assigned session id is retained with a warning when Herdr cannot expose it; `STRAW_BOSS_AGENT_SESSION_WAIT_SECONDS` bounds the lookup (default 15s).

## When a launch fails

Read the returned classification, pane excerpt, and `.launch-failure.json`.
The launcher owns bounded retries for transient missing/busy pane or agent errors, and refreshes a spent Claude session id while the instruction remains pending.
A configuration, identity, tab, or startup-gate failure requires resolving its reported cause before retrying.

Retained panes have actionable live state: a startup gate, an undelivered opening prompt, or delivered work whose bookkeeping failed.
Continue recovery in that pane.
For a provider gate, use its observed choices and the user/provider's authorization; the launcher reports an unrecognized blocked state with its actual output.

A successful launch clears the prior failure artifact.
Wrap-up archives it otherwise.

## Roll call

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/roll-call.py" [--mine] [--json]
```

This is a pure read.
It reconciles instructions, launch receipts/failures, and live provider fingerprints plus `agent_status`.
Codex uses the recorded session when present and exact terminal matching for legacy instructions.
A pane title or cwd supplies context, not identity.

| Verdict | Meaning |
|---|---|
| `running` / `checkpoint` | A matching live worker is working or waiting. |
| `awaiting-collection` | The worker's recorded status is terminal. |
| `orphaned` | No live agent matches the recorded worker fingerprint. |
| `never-launched` | Pending instruction, with any recorded failure reason. |
| `launched-unconfirmed` | A matching worker exists but confirmation is incomplete. |
| `awaiting-startup-gate` | The failed launch retained a pane awaiting action. |

Rows identify the main agent and any loss of its liveness.
Live agents in the same cwd are reported as context, without attributing them to the instruction.
Unmatched agents are `coordinator` when dispatch identity establishes that role, otherwise `unattributed` (ownership unresolved).

`--mine` requires this session's verified identity and narrows the dispatch list while retaining machine-wide attribution.

## Reporting and communication

Worker reports use [notifying-main-agent](../../notifying-main-agent/SKILL.md); coordinator replies, redirects, cancellation, and rebind use [cross-session coordination](cross-session-coordination.md).
Public scripts validate the instruction's provider fingerprint and record delivery.
Persisted status remains available after a notification failure.

## Recover a closed worker

When [wrap-up](../SKILL.md#wrap-up) finds a closed worker with missing or non-terminal status:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/recover-task-status.py" \
  --instruction-path <path> --status done|failed --note "<evidence-backed outcome>"
```

The command validates the live main agent, confirms the worker pane is unreachable, and records `recovered_by_main_agent`.
It refuses a reachable worker or an existing terminal status.
Determine the outcome from work evidence; pane closure alone establishes only reachability.

## Worker-owned coworker

Use [bringing-coworker](../../bringing-coworker/SKILL.md) for an interactive worker's second opinion or disjoint support.
Its facade owns parent identity, placement, and delivery.
