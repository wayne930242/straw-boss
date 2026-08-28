---
name: choosing-graph
description: Pick the coordination graph and the reality anchor before work starts — how the agents on this task are wired, and what contact with reality will prove the result. Use at the start of any straw-boss work, whether a main agent is about to dispatch or a dispatched worker is about to begin its own task, and again when the shape of the work changes under you.
---

## Overview

Two choices, made before the first turn of real work and stated out loud: the
**coordination graph** — how the agents on this task are wired — and the
**reality anchor** — the contact with reality that proves the result. Both are
coordination, so a main agent fixes both when it dispatches and the anchor
travels with the brief. A dispatched worker states its own graph for its own
task and works inside the anchor it was handed.

**Naming the anchor is not naming the tests.** The anchor fixes the category and
its checkpoint; inside it the worker and the user choose the method — which
seam, which cases, which tool. That split is `docs/roles.md`'s, and it is what
keeps the brief clear of the worker's own work definition.

Both are stated, not asked. The single exception is the human anchor's question
below.

## Coordination graphs

Which one applies is observable: how many app-rooted workers run under one
coordination loop, and by what mechanism.

- **single-loop** — one agent carries the work end to end. A coordinator
  driving a single dispatch's lifecycle events is still this shape, and so is a
  worker that brought one coworker. Reach for it when the work is uncomplicated
  and its length is visible from here.
- **sub-agent fan-out/fan-in** — the working agent spawns subagents through its
  own `Agent` tool and integrates what comes back. A main agent and a dispatched
  worker both use this one. Reach for it when the goal is already clear and the
  scope has converged, so every branch can be stated in full before any of them
  starts.
- **orchestrator-worker** — the coordinator dispatches more than one app-rooted
  worker and runs the loop over their status events. A confirmed dependency
  graph and a capped batch are both this shape, whether or not the workflow is
  still settling. It is the only graph that writes
  `~/.straw-boss/plans/<slug>/plan.json`; the other two carry no dispatch plan.

`orchestrator-worker` is settled ahead of the other two: more than one
app-rooted worker under one coordination loop is that shape whatever else runs
beside it, because it alone writes the dispatch plan. Subagents the coordinator
runs alongside those workers do not move it.

Between **single-loop** and **sub-agent fan-out/fan-in**, the deciding question
is whether a branch of the work itself runs in a subagent: if one does, the
shape is fan-out. The anchor's own check — including an independent review
agent — is not a branch of the work and never changes the graph.

## Reality anchors

- **testing** — the default. Unit tests at the smallest credible seam that can
  go red before the change; the worker escalates to integration or E2E when the
  target project's own conventions call for it.
- **pseudo-human** — a computer or browser drives the real interface and
  verifies a simple element by screenshot and measurement.
- **human** — the user operates the real artifact and judges it: a new UI
  element, a UX behaviour. When this is the anchor, ask the user whether their
  own risk judgment prefers pseudo-human instead. Reading code or a document is
  review, not this anchor — with nothing to operate, use the one below.
- **adversarial-review** — an independent agent attacks the finished result and
  reports what it breaks. Independent means fresh context: hand it the result
  and the requirement, never your own reasoning about them. Every ordinary
  programming change carries adversarial-review beside whichever anchor above
  applies, and it can serve as the anchor itself when the other three have no
  checkpoint to offer. Two routes discharge it: the worker reaches for it
  through its own `Agent` tool or `bringing-coworker`, or the main agent
  dispatches it against the committed result. The generated contract carries
  that obligation to every worker, and the skill that confirms the change landed
  confirms the review happened too — `shipping-task` Task 6, and `boss-say`
  Task 7 for a batch item.

Read-only work — an audit, research, a separate diagnosis — has no artifact to
operate and no change to go red, so adversarial-review is its anchor. What that
independent agent attacks is the report's claims against the evidence references
`inspecting-app`, `investigating-app`, and `troubleshooting-app`'s integration
preflight already require. Those references make the attack possible; they are
not the anchor. `troubleshooting-app`'s other branch lands a fix, so it takes
the testing anchor like any other change.

## The port a frontend anchor needs

A human or pseudo-human check on a frontend needs something running at a known
address before there is anything to look at, so the main agent claims the port
at dispatch and the worker binds it. Mechanics, the reason the worker does not
re-claim, and the release step:
`${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/shared-resource-coordination.md`.

**Verification:** the graph and the anchor are both named before work starts;
`plan.json` exists only under orchestrator-worker; a frontend human or
pseudo-human anchor carries an assigned port in the dispatch instruction; the
brief names the anchor and leaves the method inside it to the worker; an
ordinary programming change has an adversarial review beside its anchor, run by
the worker or dispatched by the main agent.
