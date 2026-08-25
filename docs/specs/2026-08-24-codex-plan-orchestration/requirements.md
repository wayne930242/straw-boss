# Codex Plan orchestration requirements

> Historical record. Live transport requirements are superseded by
> `docs/specs/2026-08-25-dispatched-agent-lifecycle-transport/`.

## Outcome and actors

Straw Boss must allow a main agent to place a Codex dispatched agent in the
same dependency-tracked Plan used by Claude dispatched agents. The main agent
owns wave scheduling; each dispatched agent owns only its own status report.

## In scope

- Mixed-agent Plans (`claude` and `codex`) using the existing `plan.json`
  dependency graph.
- Explicit main-agent provider and reachability metadata on every new dispatch;
  worker provider alone must never determine the notification transport.
- `herdr agent prompt` as the primary live notification path whenever the main
  agent has a recorded herdr pane, for every Claude/Codex worker/main-agent
  combination.
- `herdr agent prompt` as the primary lateral question path whenever another
  dispatched Claude or Codex peer has a recorded herdr pane.
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
6. A Claude worker dispatched by a Codex main agent reports through the main
   agent's herdr pane and is never told to call Claude `SendMessage`.
7. A Codex worker reports a terminal state through the same worker-facing
   command; the command persists the state before prompting the main agent's
   herdr pane.
8. `SendMessage` is available only when both the dispatched agent and main
   agent are Claude. Cross-provider dispatch data cannot record that channel.
9. A dispatched agent asks a Claude or Codex `herdr-pane` peer through its
   recorded pane id. It considers `SendMessage` only after herdr failure and
   only when both peers are Claude.

## Confirmed decisions

- `plan.json` remains provider-neutral; the dispatch instruction remains the
  source of the resolved `agent_kind` and session id.
- Persisted status plus an active status-change watcher is authoritative for
  Plan scheduling. A recorded herdr pane is the primary live notification
  channel; persisted status and the watcher remain the recovery path.
- `SendMessage` is a Claude-to-Claude-only fallback when no usable herdr pane
  exists or a herdr prompt fails. It is never a cross-provider transport.
- The same transport invariant applies vertically to main-agent reports and
  laterally to peer questions; role direction does not create an exception.
- The existing `report-task-status.py --instruction-path` command remains the
  only worker-facing status interface and now owns both ordered persistence and
  herdr notification.
- Every new dispatch explicitly records `main_agent_kind`. `herdr-pane` mode
  requires `main_agent_herdr_pane_id`; a `main_agent_send_message_peer` is valid
  only when both agent kinds are Claude.
- User confirmation: 2026-08-24, following the diagnosis and proposed
  provider-neutral correction in this conversation, refined by the user's
  decision that herdr is primary and `SendMessage` is Claude-to-Claude only.

## Open questions

None.
