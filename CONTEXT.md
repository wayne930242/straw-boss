# straw-boss

Canonical actor names and authority live in `docs/roles.md`.

## Working model

**Use the smallest sufficient loop.** The main agent carries bounded work directly. When a separate workroom is useful, it selects dispatch mechanics, schedules dependencies, names the reality anchor, acts on status events, and cleans up. Once work is dispatched, that agent discovers target-app context and owns the specification, design, implementation, and the verification method inside the reality anchor with the user.

Once work is dispatched, target-app investigation stays in that workroom and returns an explanatory conclusion with evidence references. A confirmed lower-tier work route is appropriate for bounded fact gathering.

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

Main agents order work through **ADAAV**: align outcome and user terms, continue
confirmed state, name the reality anchor, implement, verify. The ordering stays
implicit unless a real gap, handoff, decision, or result needs to be surfaced.

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
or orchestrator-worker. The coordinator states it before it dispatches; a
dispatched agent states its own for its own task.
_Avoid_: topology, supervisor-worker

**Dispatch shape**:
How much work goes out at once — one item to a specialist skill, a capped
batch in this turn, or a self-paced `/loop` batch. `boss-say` picks it; it
answers a different question from the coordination graph and neither renames
the other.

**Orchestrator handoff**:
An explicitly user-approved transfer of one work scope to a receiving main agent
in an independent Herdr tab. Acceptance moves ownership; the original keeps only
the scope named as retained.
_Avoid_: worker dispatch, delegation, shared ownership

**Continuity payload**:
The minimal executable state carried across an orchestrator handoff: goal and
scope, confirmed decisions and user terms, current state and evidence, next
action, and exclusions.
_Avoid_: transcript, conversation summary

**Reality anchor**:
The contact with reality that proves a result. The main agent names which one
and arranges its checkpoint; the worker and user choose the method inside it.
_Avoid_: acceptance gate, verification strategy

**Team-mode / solo-mode**:
The two git lifecycle shapes, picked from how the user regards the work:
worktree → develop → MR → merge → archive, or a direct commit to the base
branch.
_Avoid_: full flow, light flow
