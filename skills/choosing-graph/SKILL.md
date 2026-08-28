---
name: choosing-graph
description: Pick the coordination graph and the reality anchor before work starts — how the agents on this task are wired, and what contact with reality will prove the result. Use at the start of any straw-boss work, whether a main agent is about to dispatch or a dispatched worker is about to begin its own task, and again when the shape of the work changes under you.
---

## Overview

Two choices, made before the first turn of real work and stated out loud: the **coordination graph** — how the agents on this task are wired — and the **reality anchor** — the contact with reality that proves the result. Both are coordination, so a main agent fixes both when it dispatches and the anchor travels with the brief. A dispatched worker states its own graph for its own task and works inside the anchor it was handed.

**Naming the anchor is not naming the tests.** The anchor fixes the category and its checkpoint; inside it the worker and the user choose the method — which seam, which cases, which tool. That split is `docs/roles.md`'s, and it keeps the brief clear of the worker's own work definition.

Both are stated, not asked. The human anchor carries the one user question described below.

## Coordination graphs

Which graph applies follows from how the work actually runs.

- **single-loop** — one agent carries uncomplicated work whose length is visible end to end. A coordinator driving one dispatch's lifecycle, or a worker using one coworker as a check, remains a single loop.
- **sub-agent fan-out/fan-in** — a main agent or dispatched worker sends clear, converged branches to subagents and integrates their results.
- **orchestrator-worker** — the coordinator runs multiple app-rooted workers through status events. A dependency graph and a capped batch use this shape. It is the only graph that writes `~/.straw-boss/plans/<slug>/plan.json`; the other two carry no dispatch plan.

`orchestrator-worker` is settled ahead of the other two: more than one app-rooted worker under one coordination loop keeps that shape whatever else runs beside it.

`single-loop` and `sub-agent fan-out/fan-in` create no `plan.json` and no repo-internal Straw Boss planning or spec document. An app-rooted dispatch still writes its own `~/.straw-boss/dispatch/<app>--<slug>.json` instruction and `.contract.md`; these are the dispatch's lifecycle record, archived once the dispatch wraps up.

Between **single-loop** and **sub-agent fan-out/fan-in**, the deciding question is whether a branch of the work itself runs in a subagent: if one does, the shape is fan-out. The anchor's own check — including an independent review agent — is not a branch of the work and never changes the graph.

## Reality anchors

- **testing** — the default. Unit tests cover the smallest credible seam that can go red before the change; the worker escalates to integration or E2E when the target project's own conventions call for it.
- **pseudo-human** — a computer or browser drives the real interface and verifies a simple element by screenshot and measurement.
- **human** — the user operates the real artifact and judges a new UI element, UX behaviour, or finished article. Ask whether their risk judgment prefers pseudo-human instead. Reading code or a document is review, not a human anchor.
- **adversarial-review** — a fresh-context agent attacks the finished result against the requirement and evidence. It is the anchor when the other three offer no credible checkpoint, and accompanies an ordinary programming change as an independent check.

Review one coherent change-set with one adversarial review after implementation and primary verification. The reviewer examines the finished change-set directly. Correctness and contract findings return to the working loop; nits close with an explicit disposition. The lifecycle owner records the review once against the confirmed completion reference.

For read-only work with no operable artifact or red test, adversarial-review is its anchor. The reviewer attacks the report's claims against its evidence references. A troubleshooting branch that lands a fix uses testing like any other change.

## The port a frontend anchor needs

A frontend human or pseudo-human anchor needs a running address, so the main agent assigns the port at dispatch and the worker binds it. Claim and release mechanics live in `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/shared-resource-coordination.md`.

**Verification:** the graph and anchor are named before work starts; `plan.json` exists only under orchestrator-worker; a frontend human or pseudo-human anchor carries an assigned port; the brief leaves the method to the worker; one coherent programming change-set receives one independently dispositioned review.
