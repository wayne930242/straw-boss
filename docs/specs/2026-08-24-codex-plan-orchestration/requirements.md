# Codex Plan orchestration requirements

## Outcome and actors

Straw Boss must allow a main agent to place a Codex dispatched agent in the
same dependency-tracked Plan used by Claude dispatched agents. The main agent
owns wave scheduling; each dispatched agent owns only its own status report.

## In scope

- Mixed-agent Plans (`claude` and `codex`) using the existing `plan.json`
  dependency graph.
- Provider-neutral status-change detection that notices every transition of a
  task's status file, including checkpoint-to-terminal transitions.
- Codex `herdr-pane` checkpoint replies and documented headless continuation
  through the recorded Codex thread id.
- Existing Claude behavior and permission mapping remain compatible.

## Out of scope

- Adding an agent kind other than the currently supported `claude` and `codex`.
- Changing merge, other-branch-push, tracker, or shared-resource authority.
- Automatically deciding user-owned work-content questions.

## Scenarios

1. `t1` runs under Codex, reports `done`, and automatically makes dependent
   `t2` ready.
2. A Codex task reports `awaiting-main-agent`; the main agent replies into its
   existing herdr pane, after which a later `done` transition is detected.
3. A task status file changes from any checkpoint to `done` or `failed`; the
   watcher emits the later transition instead of deduplicating by filename.
4. Restarting the watcher emits the current persisted status once, allowing a
   resumed main agent to recover the Plan state.
5. Existing Claude Plan dispatch continues to work unchanged.

## Confirmed decisions

- `plan.json` remains provider-neutral; the dispatch instruction remains the
  source of the resolved `agent_kind` and session id.
- Persisted status plus an active status-change watcher is authoritative for
  Plan scheduling. Claude `SendMessage` remains an additive fast path.
- The existing `report-task-status.py --instruction-path` command is the only
  worker-facing status-write interface.
- User confirmation: 2026-08-24, following the diagnosis and proposed
  provider-neutral correction in this conversation.

## Open questions

None.
