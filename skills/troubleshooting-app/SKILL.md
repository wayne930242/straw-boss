---
name: troubleshooting-app
description: Use when something is broken and the cause is unknown, scoped to one of the project's managed apps, e.g. "X is failing", "500 in production for app-name" — not for a known task with a clear fix already in mind (`boss-say`), a rule/convention audit (inspecting-app), or open-ended research into current behavior with no reported failure (investigating-app).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework this skill operates under — not redefined here.

No worktree opened yet, no fix made yet — the cause is unknown, so there's
nothing to branch for and nothing to patch. Managed-app diagnosis always
dispatches to a worker rooted in that app so its code, logs, tests, and agent
system do not load into the main agent's coordination context. Once root cause
is known, hand off to `boss-say` for the actual fix.

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
- **App-level or uncertain:** continue to Task 3. The dispatched diagnosis can
  distinguish an app cause from an external dependency using its actual evidence.

**Verification:** classification cites supplied evidence; uncertainty dispatches
instead of prompting the main agent to inspect another project.

## Task 3: Diagnose

Send the diagnosis through `dispatching-work` as a worker rooted in the app's
directory, diagnosis only. A bounded diagnosis may resolve to a confirmed
lower-tier work route, but do not invent a model choice outside that route.

Frame the task around the failure mechanism and root cause to explain. Require
reproduction observations and evidence references to logs, tests, commands,
files, or artifacts. The deliverable is an explanatory, falsifiable root-cause
account. The worker
reports through `report-task-status.py --instruction-path <path> --status done
--note "<root cause>" --ref "<evidence>"`, which writes before notifying the
recorded main-agent herdr pane. It never invokes `boss-say` or dispatches anything
itself.

Target-app file access and reproduction stay inside the worker. This task ends
with a root-cause account; implementation is routed separately.

**Verification:** the dispatched report states a specific root cause or an
explicitly exhausted hypothesis set, includes evidence references, and never
escalates to a fix on its own.

## Task 4: Hand off to the fix

Once root cause is known from a dispatched worker's completion report, tell the
user and hand the requested fix to `boss-say`, which owns its scale and
execution-tier decision.

**Verification:** any code change is handed to `boss-say`, not made inline here.
