# Roles & Authority

This is the single execution-time definition of who decides what.

## Cast

**User** — owns the requested outcome and authorization.
The user is the actual "boss" in Straw Boss naming.

**Main agent** — owns routing and coordination. In a bounded single-loop it also owns the work; when it dispatches, it owns mechanics, scheduling, shared resources, status-event handling, and cleanup.

An **orchestrator handoff** moves an explicit scope between two main agents in
separate Herdr tabs. Because it creates another user-facing window, the current
main agent first presents one approval decision. Ownership moves when the
receiving orchestrator accepts and routes that scope through `boss-say`; the
original then owns only its retained scope. With no retained scope, it reports
the accepted handoff and closes its own pane.

**Dispatched agent** — an independent task owner once launched through Herdr. It
works in the target app with that app's harness. The user and dispatched agent
decide the specification, design, implementation, and the verification method
inside the reality anchor the dispatch names (Authority boundary below). The
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

**Use the smallest sufficient loop.** The main agent may carry bounded work end to end. Once work is dispatched, it supplies the requirement and known coordination facts; target-app discovery and work definition belong to the dispatched agent and user, while the main agent keeps the coordination loop moving.

**Run ADAAV lightly.** Align the outcome and the user's terms, continue from
confirmed state, name the reality anchor, implement through the smallest loop,
then verify. This is an internal ordering rather than a response template;
surface text grows only for a real gap, handoff, decision, or result.

**The coordination graph is coordination too.** The main agent states how the
agents on a task are wired — single-loop, sub-agent fan-out/fan-in, or
orchestrator-worker — before it dispatches, and a dispatched agent states its own
for its own task. `choosing-graph` holds the criterion.

**The reality anchor is coordination; the method inside it is work.** The main
agent names which anchor proves a task — testing, pseudo-human, human, or an
independent agent's adversarial review — and arranges its checkpoint, including
any shared resource that has to exist before the worker has anything to show.
Inside that anchor the user and dispatched agent choose the method: for testing,
unit tests at the smallest credible seam that can go red before the change,
escalated to integration or E2E when the target project's own conventions call
for it. Naming the anchor is not naming the tests.

Once work is dispatched, target-app context discovery belongs to the dispatched agent. The main agent integrates its evidence-backed conclusion and references.

Main-to-worker operations serve that boundary:

- **Inform** carries a verified cross-task fact or explicit user direction.
- **Redirect** carries an explicit user change or repairs an objectively wrong
  dispatch/dependency instruction.
- **Cancel** carries explicit user direction or closes an objectively invalid,
  duplicate, or unreachable dispatch.
- **Resolve** supplies an already-known coordination fact or the result of a
  coordinator-owned action. Work-content decisions stay in the user–worker
  conversation.

If orchestration facts conflict with a decision made by the user and dispatched
agent, the main agent surfaces the conflict to the user and preserves the
worker's current direction until the user responds.

User-facing coordination reports carry only the current coordination delta and
the minimum context needed to understand it. When the next step needs a
user-owned decision, the main agent presents exactly one decision through the
harness-native ask-question interface and waits for its answer before presenting
the next decision. If that interface is unavailable, it asks one concise
plain-text question and waits.

Interactive work-detail questions and authorization stay in the dispatched
agent's pane. The main agent relays them only for a headless task. Peer messages
are factual and carry no direction or authorization.

Every dispatched agent reports terminal `done` or `failed` through
`report-task-status.py`. The command persists status before notifying the
validated main-agent Herdr endpoint; the watcher remains recovery evidence.

That persisted status and its notification are what drive the coordination
lifecycle. The main agent acts on each event — a checkpoint to resolve, a
terminal state to record, a ready dependency to schedule, a terminal dispatch to
clean up — and reads a task's live progress when observed evidence and its
recorded state actually disagree, or when the user asks what it is doing.

The main agent may autonomously schedule ready work, coordinate shared resources,
act on status events, and clean up terminal dispatches. User-gated mutations remain
user decisions. Tracker mutations remain coordinator-owned and happen only after
the relevant work is complete.

An accepted orchestrator handoff ends the original main agent's coordination of
that scope: status events, investigation, scheduling, reporting, and cleanup all
belong to the receiver. Before acceptance, the original remains the owner. A
failed acceptance is retried once; a second failure closes the new tab and
leaves ownership unchanged.
