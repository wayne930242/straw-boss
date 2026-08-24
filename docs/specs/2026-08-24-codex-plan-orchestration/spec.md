# Codex Plan orchestration specification

## Observable contract

- `dispatch-task.py write --plan ... --task-id ... --agent-kind codex --main-agent-kind ...`
  succeeds
  for a planned task, records `agent_kind: codex`, and marks only that task
  `dispatched`.
- A Codex Plan task receives the same explicit progress/status script contract
  as a Claude Plan task. It need not load a Claude-only skill to report state.
- Every new dispatch records `main_agent_kind`. `herdr-pane` dispatch refuses
  to write an instruction without the main agent's herdr pane id.
- A SendMessage peer may be recorded only when `agent_kind` and
  `main_agent_kind` are both `claude`; every other combination rejects it
  before writing an instruction or changing `plan.json`.
- `report-task-status.py --instruction-path` writes the durable status first,
  then sends a self-contained status message with `herdr agent prompt` when the
  instruction records a main-agent pane. This behavior is identical for all
  Claude/Codex worker/main-agent combinations.
- If the herdr prompt fails, the status record remains durable and the command
  exits non-zero with a clear notification error. Plan recovery continues
  through `watch-plan-status.py`; Claude-to-Claude callers may use their
  `SendMessage` fallback.
- The Plan watcher emits one event for every valid status-file content change,
  not merely the file's first appearance. A fresh watcher emits each current
  status once.
- `read-plan-status.py --ready` continues to release a dependent task only when
  every dependency is `done`.
- `reply-to-worker.py` accepts any supported `herdr-pane` agent kind and keeps
  its existing delivery-confirmation and resolution-record guarantees.
- A headless Codex checkpoint is continued with the instruction's recorded
  thread id through `codex exec resume`; a non-interactive task that cannot
  provide a durable checkpoint report is treated as failed, never silently
  complete.
- `asking-peer-agents` prompts the recorded `herdr_pane_id` directly for either
  a Claude or Codex peer. It may resolve a Claude peer name and call
  `SendMessage` only as a Claude-to-Claude fallback after herdr fails.

## Compatibility and edge cases

- Existing instruction files without new fields remain readable.
- The legacy `--plan/--task` status form continues to write durable status but
  cannot send a live notification because it has no instruction reachability.
- Main-agent-authored `cancelled` writes do not prompt the main agent's own pane.
- Unknown agent kinds remain rejected by the CLI's enumerated choices.
- Malformed or partially-written status JSON does not crash the long-running
  watcher; it is retried on a later scan.
- A watch event's `task_id` comes from the status filename; payload content
  cannot redirect an event to a different task.
- `failed` and `cancelled` never satisfy a dependency.
- Authorization and user-input statuses remain non-terminal and retain their
  existing authority boundaries.

## Non-goals

- Status events do not grant authorization.
- Plan workers never write `plan.json` directly.
- This change does not make Codex addressable through Claude `SendMessage` or
  `ListAgents`.
- This change does not emulate or shell out to Claude `SendMessage`; that tool
  remains available only inside a Claude-to-Claude agent interaction.

## Applied standards and precedent

- `AGENTS.md` working agreements supplied in the session: read before write,
  scoped changes, relevant verification, Traditional Chinese communication.
- `CONTEXT.md`: the main agent owns dispatch authority; dispatched agents own
  their outcomes.
- `openspec/specs/agent-kind-dispatch/spec.md`: existing supported agent-kind
  selection and permission guarantees.
- `scripts/report-task-status.py` and `scripts/read-plan-status.py`: existing
  provider-neutral persisted-state and ready-wave seams.

## Correctness strategy

Python standard-library integration tests invoke the real script CLIs in an
isolated temporary home directory with a fake `herdr` executable. They prove
dispatch validation for every provider pairing, status-before-prompt ordering,
Codex/Claude herdr delivery, Codex status unblocking, repeated status-transition
detection, restart recovery, Codex herdr-pane checkpoint reply behavior, and the
peer-question transport contract. No human appropriateness check is needed.
