# Agent communication contract requirements

## Outcome and actors

Straw Boss must keep dispatch prompts short while making agent messages
actionable and authority-safe. The main agent owns task direction; dispatched
agents discuss work details and authorization directly with the user; peers may
exchange information only.

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

## Out of scope

- Replacing Herdr or changing dispatch modes.
- Rewriting existing immutable dispatch contracts.
- Adding verbose prompt templates or task-specific implementation checklists.
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

## Confirmed decisions

- Prefer deletion and single-source rules over adding repeated reminders.
- Enforce authority in scripts; skills only select the semantic operation.
- Preserve free-text task briefs and notes, with a small required content
  contract rather than a large schema.
- The user is the default conversation owner for detail and authorization; the
  main agent is a relay and context integrator, not a substitute decision maker.
- User confirmation: 2026-08-26, by requesting the fixes and prioritizing shorter
  skills.

## Open questions

None.
