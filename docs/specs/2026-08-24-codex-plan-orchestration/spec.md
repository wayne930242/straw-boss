# Codex Plan orchestration specification

## Observable contract

- `dispatch-task.py write --plan ... --task-id ... --agent-kind codex` succeeds
  for a planned task, records `agent_kind: codex`, and marks only that task
  `dispatched`.
- A Codex Plan task receives the same explicit progress/status script contract
  as a Claude Plan task. It need not load a Claude-only skill to report state.
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

## Compatibility and edge cases

- Existing instruction files without new fields remain readable.
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
isolated temporary home directory. They prove Codex Plan dispatch, Codex status
unblocking, repeated status-transition detection, restart recovery, and Codex
herdr-pane checkpoint reply behavior. No human appropriateness check is needed.
