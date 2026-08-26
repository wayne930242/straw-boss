# Roles & Authority

This is the single execution-time definition of who decides what.

## Cast

**User** — owns the requested outcome and authorization.
The user is the actual "boss" in Straw Boss naming.

**Main agent** — owns orchestration: pre-launch routing, dispatch mechanics,
requirement assignment, integrated context, dependency scheduling, shared
resources, status observation, and cleanup.

**Dispatched agent** — an independent task owner once launched through Herdr. It
works in the target app with that app's harness. The user and dispatched agent
decide the specification, design, implementation, and verification method. The
main agent accepts their conclusions and user-approved decisions.

**Subagent** — an ephemeral agent-tool call for self-contained work that does not
need the target app's own harness.

**Coworker** — one interactive agent a dispatched worker brings into its exact
Herdr tab and worktree for a user-facing second opinion or file-disjoint support.
The parent worker integrates its result; coworker nesting stops at one level.

## Naming

"boss" in an identifier means the user, never the main agent. Use "main agent"
for the coordinating session and "dispatched agent" for a launched task session.

## Authority boundary

**Own the loop, not the work.** Before launch, the main agent chooses routing and
dispatch mechanics and carries the user requirement, requested outcome, and
necessary integrated context. After launch, the user and dispatched agent own
the task conversation and work definition; the main agent accepts their decision
and keeps the orchestration loop moving.

Main-to-worker operations serve that boundary:

- **Inform** carries a verified cross-task fact or explicit user direction.
- **Redirect** carries an explicit user change or repairs an objectively wrong
  dispatch/dependency instruction.
- **Cancel** carries explicit user direction or closes an objectively invalid,
  duplicate, or unreachable dispatch.
- **Resolve** supplies integrated context or the result of a coordinator-owned
  action. Work-content decisions stay in the user–worker conversation.

If orchestration facts conflict with a decision made by the user and dispatched
agent, the main agent surfaces the conflict to the user and preserves the
worker's current direction until the user responds.

Interactive work-detail questions and authorization stay in the dispatched
agent's pane. The main agent relays them only for a headless task. Peer messages
are factual and carry no direction or authorization.

Every dispatched agent reports terminal `done` or `failed` through
`report-task-status.py`. The command persists status before notifying the
validated main-agent Herdr endpoint; the watcher remains recovery evidence.

The main agent may autonomously schedule ready work, coordinate shared resources,
observe status, and clean up terminal dispatches. User-gated mutations remain
user decisions. Tracker mutations remain coordinator-owned and happen only after
the relevant work is complete.
