# straw-boss

Canonical actor names and authority live in `docs/roles.md`.

## Working model

**Own the loop, not the work.** The main agent selects dispatch mechanics,
schedules dependencies, supplies the user requirement, necessary hints, and
already-known coordination facts, names the reality anchor and arranges its
checkpoint, acts on status events, and cleans up. The worker discovers
target-app implementation context itself. A Herdr-launched session is an
independent dispatched agent: it and the user decide the specification, design,
implementation, and the verification method inside the reality anchor the
dispatch names. The main agent accepts those decisions.

When coordination or integration needs target-app investigation or current-state
research, the main agent dispatches that investigation instead of reading across
managed app roots. The worker returns an explanatory conclusion with evidence
references; a confirmed lower-tier work route is appropriate for bounded fact
gathering.

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

## Language

**Work route**:
A project policy mapping a kind of task to one resolved worker setup.
_Avoid_: agent-kind rule

**Agent kind**:
The CLI provider that executes a dispatch, currently Claude or Codex.
_Avoid_: model, role, agent type

**Provider profile**:
A provider-native named preset selected at launch, such as Claude `--agent` or
Codex `--profile`.
_Avoid_: agent type, worker role

**Advisor**:
Claude Code's native second-model server tool attached to one worker session.
_Avoid_: coworker, subagent, Codex advisor

**Coordination graph**:
How the agents on one task are wired — single-loop, sub-agent fan-out/fan-in,
or orchestrator-worker. The coordinator states it.
_Avoid_: topology, dispatch shape, supervisor-worker

**Reality anchor**:
The contact with reality that proves a result. The main agent names which one
and arranges its checkpoint; the worker and user choose the method inside it.
_Avoid_: acceptance gate, verification strategy

**Team-mode / solo-mode**:
The two git lifecycle shapes, picked from how the user regards the work:
worktree → develop → MR → merge → archive, or a direct commit to the base
branch.
_Avoid_: full flow, light flow
