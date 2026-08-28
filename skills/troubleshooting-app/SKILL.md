---
name: troubleshooting-app
description: Use when something is broken and the cause is unknown in a managed app. Ordinary failures keep diagnosis and repair in one shipping-task worker; integration diagnosis that must prepare later dispatches runs as a separate preflight investigation.
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework this skill operates under — not redefined here.

A reported failure is expected to end fixed, not merely explained. By default,
diagnosis and repair run continuously inside one `shipping-task` worker: it is
already rooted in the app, with the main agent's own permission tier mirrored
onto it, so a second dispatch only restarts cold and re-derives what the first
worker already learned.

An **integration preflight** is the exception. Split diagnosis into its own
dispatch only when both conditions hold: the failure crosses an integration
boundary, and its explanatory conclusion is needed to shape or schedule later
dispatches. The separate result gives the main agent evidence-backed coordination
input before it commits workers to the wrong apps or dependency order. An
integration symptom that one resolved app can diagnose and repair does not meet
that bar; it stays in the same worker.

What the split used to protect is unaffected: the main agent still never loads
the app's code, logs, or agent system into its coordination context. Dispatching
achieves that on its own, whether or not the worker goes on to fix what it found.

The fix runs through `shipping-task`'s existing git lifecycle, so its gates are
unchanged — commit and the task's own feature-branch push need no authorization,
merge and any other-branch push still stop for the user.

When the continuous worker discovers that the cause belongs to data,
configuration, infrastructure, or another app, it delivers the root-cause
account and says so. That is a complete result for this app and supplies the
evidence for the next route.

## Task 1: Resolve the app

Invoke `work-on` now. Even for a live incident, you need the target app before digging in.

**Verification:** the target app is established before Task 2.

## Task 2: App-code or infrastructure?

Classify only from evidence the user already supplied; do not read app or
infrastructure files from the main-agent session to enrich this classification.
Symptoms like "works locally, fails in an environment", "worked yesterday, no
code changed", or "500 with no recent deploy to this app" can point at
infrastructure rather than code.

- **Clearly infra-level from supplied evidence:** hand off to this project's
  infrastructure/ops skill or team if one exists; otherwise report the boundary.
- **App-level or uncertain:** continue to Task 3. The target-app worker can
  distinguish an app cause from an external dependency using its actual evidence.

**Verification:** classification cites supplied evidence; uncertainty dispatches
instead of prompting the main agent to inspect another project.

## Task 3: Choose the continuous or preflight branch

Use an integration preflight only when the supplied evidence already shows both
parts of the exception: an integration boundary and a diagnosis needed before
later work can be routed or scheduled. Dispatch that diagnosis through
`dispatching-work`, rooted in the resolved app, and require an explanatory,
falsifiable root-cause account with evidence references to logs, tests, commands,
files, or artifacts. The result must identify the affected boundary and the
downstream work or dependency order it enables.

For every other app-level or uncertain failure, hand the cause-plus-fix outcome
to `shipping-task` with the app already resolved. It owns the mode decision,
worktree creation, dispatch, and authorization gates. One worker reproduces the
failure, explains its mechanism and root cause, and repairs it without a second
cold start.

On the continuous branch, frame the brief around the failure mechanism and root
cause the worker must explain, then fix. Require reproduction observations and
evidence references — a fix landing without an articulated cause is a guess, and
this skill exists because the cause was unknown.

Carry any hypothesis the user already eliminated and the reason, so the worker
does not spend a cycle re-deriving it.

Scope is unknown on the continuous branch — that is this skill's premise, not an
oversight. `shipping-task` Task 2 still asks its own question at handover: how
the user regards this work, which they can answer before the cause is known.

Everything else about either brief follows the same boundary: target-app context
discovery and reproduction belong to the worker; implementation belongs to the
continuous worker or a later task informed by the preflight result.

**Verification:** a separate diagnosis has both integration-preflight conditions
recorded and names the later routing decision it enables; every other brief names
both the cause to explain and the fix to land in one worker. The user's eliminated
hypotheses are carried forward and discovery stays with the worker.

## Task 4: Confirm the outcome

On the continuous branch, `shipping-task` carries the lifecycle to completion
and wraps up its own dispatch. Confirm that the reported symptom has a stated
cause with evidence behind it, not just a diff that makes the symptom stop.

On the integration-preflight branch, integrate the worker's explanatory
conclusion and evidence references, then route or schedule the enabled work. A
single-app fix goes through `shipping-task`; multiple dependent tasks return to
`boss-say` with their dependency facts.

When the worker reports the cause lies outside this app, relay the account and
route the follow-up — a different app goes back through `boss-say`,
infrastructure through Task 2's boundary.

**Verification:** the continuous result names the root cause with evidence, not
only the change made; an integration preflight leads to the downstream dispatch
or an explicit user-owned blocker, and a cause outside this app is routed rather
than dropped.
