# straw-boss

Canonical actor names and authority live in `docs/roles.md`.

## Working model

**Own the loop, not the work.** The main agent selects dispatch mechanics,
schedules dependencies, supplies the user requirement and necessary integrated
context, observes status, and cleans up. A Herdr-launched session is an
independent agent: it and the user decide the specification, design,
implementation, and verification method. The main agent accepts those decisions.

Main-to-worker communication carries explicit user direction, verified
cross-task facts, or coordinator-owned action results. A conflict returns to the
user; it is not independently decided by the main agent.

Live agent-to-agent bodies carry one new fact, question, answer, or action in at
most two sentences. Detailed context and evidence travel as references.

Terminal `done` and `failed` reports persist first, then notify the validated
main-agent Herdr endpoint.

An interactive dispatched agent may bring one coworker into the same tab and
worktree. Coworkers default to review-only, talk with the user directly, and
notify both parent and root coordinator on `done` or `failed`.

In identifiers, "boss" means the user. Prose uses **main agent**, **dispatched
agent**, and **subagent** for the three agent roles.
