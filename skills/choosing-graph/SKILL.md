---
name: choosing-graph
description: Pick the coordination graph and the reality anchor before work starts — how the agents on this task are wired, and what contact with reality will prove the result. Use at the start of any straw-boss work, whether a main agent is about to dispatch or a dispatched worker is about to begin its own task, and again when the shape of the work changes under you.
---

## Overview

Two choices, made before the first turn of real work and stated out loud: the
**coordination graph** — how the agents on this task are wired — and the
**reality anchor** — the contact with reality that proves the result. A main
agent fixes both when it dispatches. A dispatched worker picks its own graph for
its own task and confirms the anchor it was handed.

Both are stated, not asked. The single exception is the human anchor's question
below.

## Coordination graphs

- **single-loop** — one agent carries the work end to end and nothing else is
  scheduled against it; a coordinator handling one dispatch's own lifecycle
  events is still this shape. Reach for it when the work is uncomplicated and
  its length is visible from here.
- **sub-agent fan-out/fan-in** — the working agent spawns subagents through its
  own `Agent` tool and integrates what comes back. A main agent and a dispatched
  worker both use this one. Reach for it when the goal is already clear and the
  scope has converged, so every branch can be stated in full before any of them
  starts.
- **orchestrator-worker** — the coordinator dispatches app-rooted workers and
  runs the loop over their status events, and each worker carries part of that
  coordination loop itself. This is the coordinator's shape alone; a dispatched
  worker picks one of the other two. Reach for it when the workflow is still
  unstable — when what the next task should be depends on what the last one
  found. It is also the graph that writes
  `~/.straw-boss/plans/<slug>/plan.json`. The other two carry no dispatch plan.

## Reality anchors

- **testing** — the default. Unit tests at the smallest credible seam that can
  go red before the change; the worker escalates to integration or E2E when the
  target project's own conventions call for it.
- **pseudo-human** — a computer or browser drives the real interface and
  verifies a simple element by screenshot and measurement.
- **human** — the user judges the real artifact: a new UI element, a UX
  behaviour, or a finished article. When this is the anchor, ask the user
  whether their own risk judgment prefers pseudo-human instead. A human reading
  code or a document is review, and review is never the anchor.
- **adversarial-review** — an independent agent attacks the finished result and
  reports what it breaks. Independent means fresh context: hand it the result and
  the requirement, never your own reasoning about them. Every ordinary programming change carries
  adversarial-review beside whichever anchor above applies, and it becomes the
  anchor itself when the other three have no checkpoint to offer. A dispatched
  worker reaches for it through its own `Agent` tool or `bringing-coworker`.

## The port a frontend anchor needs

A human or pseudo-human check on a frontend needs something running at a known
address before anyone can look at it. The main agent claims the port as part of
the dispatch — one `claim-port` call keyed on the dispatch instruction stem or
the app's checkout path — and states the assigned number in the instruction. The
worker binds that number without claiming again, since its own listener reads as
an external occupant on a second probe. The claim is released at wrap-up.

Mechanics: `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/shared-resource-coordination.md`.

**Verification:** the graph and the anchor are both named before work starts;
`plan.json` exists only under orchestrator-worker; a frontend human or
pseudo-human anchor carries an assigned port in the dispatch instruction.
