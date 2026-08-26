# Agent communication contract requirements

## Outcome and actors

Straw Boss must keep dispatch prompts short while making agent messages
actionable and authority-safe. The user owns the requested outcome; after a
Herdr launch, the dispatched agent independently owns execution and discusses
work details and authorization directly with the user. The main agent owns
orchestration mechanics and accepts their decisions; peers exchange information
only.

## In scope

- Authenticate the live sender before cross-session delivery.
- Allow only role-appropriate direction and intent combinations.
- Give peer questions a verified return path and correlation id.
- Require useful checkpoint and terminal notes.
- Route detail questions and authorization to the user by default. Use the main
  agent only as a relay when no direct user channel exists, or for integrated
  instructions and context the coordinator owns.
- Add deliverable/proof and non-overlap guidance without duplicating lifecycle
  prose across skills.
- Make live agent messages delta-only: one purpose, at most two sentences, with
  long context and evidence carried as structured references.
- Remove prompt authority for the main agent to independently re-specify,
  redirect, or cancel work that the user and dispatched agent have decided.
- Require `done` and `failed` status reports to notify the recorded main-agent
  Herdr endpoint after durable persistence.
- Place every Herdr-dispatched worker pane in the coordinating main agent's
  current tab; dispatch never creates a separate tab.

## Out of scope

- Replacing Herdr or changing dispatch modes.
- Rewriting existing immutable dispatch contracts.
- Adding verbose prompt templates or task-specific implementation checklists.
- Applying the two-sentence limit to the cold-start dispatch brief; a new agent
  still needs enough objective, deliverable, boundary, and reference context.
- Providing strong process authentication for headless agents that share one OS
  account; their existing instruction-scoped durable status remains compatible.

## Scenarios

1. A peer can ask and answer another live task, with both messages tied to one id.
2. A peer cannot deliver a main-agent-only redirect.
3. A live task cannot report status for another live task.
4. A terminal or checkpoint report without an actionable note is rejected.
5. An interactive dispatched agent asks the user, not the main agent, about a
   work detail or authorization. A headless agent persists the user-owned
   checkpoint for the main agent to relay.
6. A dispatch brief states a concrete deliverable and proof only when the
   outcome and acceptance criteria do not already make them clear.
7. A live message with more than two sentences is rejected before delivery.
8. A concise message can carry one or more artifact/evidence references without
   copying their content into the body or delivery ledger.
9. Routing identity and status labels are generated once by the transport, not
   repeated in caller-authored prose.
10. Once a Herdr task launches, its main agent does not re-approve or override
    work-detail decisions made between the user and dispatched agent.
11. The main agent may relay explicit user direction, cross-task facts, or the
    result of a coordinator-owned action; a work-content conflict returns to the
    user instead of being decided by the main agent.
12. Both `done` and `failed` write durable status before notifying the recorded
    main-agent Herdr session.
13. Launching one or many Herdr workers splits new panes from the recorded main
    pane. Every launch receipt records the main pane's tab id, and no launch path
    invokes `herdr tab create`.

## Confirmed decisions

- Prefer deletion and single-source rules over adding repeated reminders.
- Enforce authority in scripts; skills only select the semantic operation.
- Preserve free-text task briefs and notes, with a small required content
  contract rather than a large schema.
- The user is the default conversation owner for detail and authorization; the
  main agent is a relay and context integrator, not a substitute decision maker.
- A Herdr dispatch is an independent agent session. The main agent owns routing,
  dependencies, observation, and cleanup—not the task's implementation choices.
- The coordinating main pane's tab is the sole visual container for its workers.
  Terminal cleanup closes worker panes only and preserves the shared tab.
- Live messages carry only the new fact, action, question, or answer. They use at
  most two sentences; longer material moves to a reference. There is no hard
  character or token limit.
- User confirmation: 2026-08-26, by requesting the fixes and prioritizing shorter
  skills; the later refinements confirmed delta-only messages, independent Herdr
  workers, and main-agent notification for `done`/`failed`.

## Open questions

None.
