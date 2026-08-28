---
name: troubleshooting-app
description: Use when something is broken and the cause is unknown in a managed app. Ordinary failures keep diagnosis and repair in one shipping-task loop; integration diagnosis that must prepare later dispatches runs as a separate preflight investigation.
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework this skill operates under — not redefined here.

A reported failure is expected to end fixed, not merely explained. Diagnosis and repair stay in one `shipping-task` single-loop so the same agent preserves the evidence and context it discovers.

An **integration preflight** is useful only when both conditions hold: the failure crosses an integration boundary, and its explanatory conclusion is needed to shape or schedule later dispatches. It supplies evidence-backed coordination input. A symptom that one resolved app can diagnose and repair stays in the same worker.

The fix runs through `shipping-task`'s git lifecycle and mode decision.

When the continuous loop locates the cause in data, configuration, infrastructure, or another app, its root-cause account and evidence supply the next route.

## Task 1: Resolve the app

Invoke `work-on` now. Even for a live incident, you need the target app before digging in.

**Verification:** the target app is established before Task 2.

## Task 2: App-code or infrastructure?

Classify from evidence the user already supplied. Symptoms such as environment-only failure, failure without an app change, or an unexplained server response can point to infrastructure.

- **Clearly infrastructure:** hand off to the project's infrastructure/ops owner with the supplied evidence.
- **App-level or uncertain:** continue to Task 3 so the target-app loop can distinguish an app cause from an external dependency.

**Verification:** the classification cites supplied evidence and uncertainty continues to the target-app loop.

## Task 3: Choose the continuous or preflight branch

Use an integration preflight only when the supplied evidence already shows the integration boundary and the later routing decision it must enable. Run it through `dispatching-work` in the resolved app and require an explanatory, falsifiable root-cause account with evidence references to logs, tests, commands, files, or artifacts. Its reality anchor is an independent agent's adversarial review of the account.

For every other app-level or uncertain failure, hand the cause-plus-fix outcome to `shipping-task` with the app already resolved. It owns the mode decision, execution tier, worktree, and authorization gates. One agent reproduces the failure, explains its mechanism and root cause, and repairs it in the same loop. The fix is anchored on testing: the reproduction goes red before the repair.

On the continuous branch, frame the work around the failure mechanism and root cause to explain, then fix. Require reproduction observations and evidence references.

Carry any hypothesis the user already eliminated and its evidence.

`shipping-task` Task 2 still asks how the user regards this work, which they can answer before the cause is known.

Target-app discovery and reproduction belong to the selected work loop; implementation stays in the continuous loop or a later task informed by the preflight.

**Verification:** a preflight records both conditions and the routing decision it enables; every other app-level or uncertain failure names both the cause to explain and the fix to land. One agent reproduces the failure and carries it through repair.

## Task 4: Confirm the outcome

On the continuous branch, `shipping-task` carries the lifecycle to completion. Confirm that the reported symptom has a stated cause with evidence behind it.

On the integration-preflight branch, integrate the explanatory conclusion and evidence references, then route the enabled work. A single-app fix goes through `shipping-task`; multiple dependent tasks return to `boss-say` with their dependency facts.

When the cause lies outside this app, route the evidence-backed account to the relevant app or infrastructure owner.

**Verification:** the continuous result names the root cause with evidence; an integration preflight leads to the downstream dispatch or a user-owned blocker; an external cause reaches its owner.
