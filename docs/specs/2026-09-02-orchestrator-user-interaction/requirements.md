# Orchestrator user interaction

## Outcome and actors

The main agent keeps its conversation with the user compact while coordination
continues. It reports only the current coordination delta. When progress needs
a user-owned decision, it asks through the harness-native ask-question interface
and resolves one decision before presenting the next.

Actors:

- The user owns decisions and authorization.
- The main agent owns coordination and presents the decision checkpoint.
- Dispatched agents continue to discuss work details with the user in their own
  interactive pane; headless checkpoints are relayed by the main agent.

## In scope

- The execution-time authority statement for main-agent communication.
- The SessionStart orchestrator stance injected into candidate main-agent
  sessions.
- Batch and dispatch checkpoint wording that currently tells the main agent how
  to report a user decision.
- Contract tests that make the interaction rule observable.
- Herdr coordinator-tab and worker-pane naming as each interactive dispatch starts.

## Out of scope

- Worker-to-worker message length and transport.
- Changing who owns a decision or authorization.
- Changing Plan status values, dispatch lifecycle, or scheduling behavior.
- Combining independent decisions into one answer.

## Scenarios

1. A dispatch starts, changes state, pushes its feature branch, or reaches a
   terminal state. The main agent reports the smallest useful coordination
   delta, without repeating background already known to the user.
2. One checkpoint needs one user decision. The main agent opens one
   harness-native ask-question prompt for that decision.
3. Several checkpoints or one checkpoint with several independent decisions
   need the user. The main agent asks the first decision, waits for its answer,
   then asks the next; it does not batch them into one prompt.
4. A dispatched interactive worker needs a work-content decision. The existing
   direct user-worker path remains authoritative; the main agent points the user
   to that pane with a compact report.
5. A headless worker needs a user decision. The main agent relays it through the
   ask-question interface one decision at a time, then continues the existing
   provider-specific resume path.
6. Before an interactive dispatch creates a worker pane, the launcher names the
   coordinator's shared tab. It then names the new pane for the dispatched work
   before submitting the task to the worker.

## Confirmed decisions

- General orchestrator updates emphasize compact reporting.
- User-owned decisions use an ask-question interaction.
- User-owned decisions are asked sequentially, one decision per prompt.
- A worker pane reuses the launcher's final collision-resolved agent name.
- The coordinator tab uses the compact app-derived coordinator identity.
- Tab and pane naming are best effort. Retry a naming failure, then dispatch anyway with
  one compact warning.

## Open questions

- None.
