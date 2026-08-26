---
name: inspecting-app
description: Use when the user wants to check or audit something against existing rules or conventions, scoped to one of the project's managed apps, e.g. "audit this module", "check if X follows the rules" — not for open-ended research into how something currently behaves with no rule in question (investigating-app), diagnosing a reported failure (troubleshooting-app), or implementing a fix (`boss-say`).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework this skill operates under — not redefined here.

Resolve the app, then dispatch the actual audit into it. A managed-app audit
always dispatches so the app's rules and agent system load only in the worker
session, not the main agent's coordination context. This skill does not
reimplement audit methodology.

## Task 1: Resolve the app

Invoke `work-on` now. Do not proceed without the target app.

- If `work-on` asked a clarifying question (an ambiguous name matching more than one app's `match` phrases) or found the request out of the project's managed-app scope, stop here and surface that to the user — don't guess an app to keep moving.
- If `work-on` named more than one app, treat Task 2 as running once per app rather than picking one arbitrarily; each app's audit is independent.

**Verification:** the target app(s) are established before Task 2, or you've surfaced `work-on`'s clarifying question / out-of-scope result instead of proceeding.

## Task 2: Dispatch an evidence-bearing audit

Send each resolved app through `dispatching-work` as a worker rooted in that
app's directory. A bounded audit may resolve to a confirmed lower-tier work
route, but do not invent a model choice outside the configured route.

Frame the audit around which rules apply, how the target behaves against them,
and what consequence follows. Require evidence references to the exact rule
source and observed implementation, test, log, or artifact. The deliverable is
an explanatory, evidence-backed assessment. The
worker decides whether to run the app's local audit skill or global `inspecting`;
the generated contract supplies instruction-keyed status and communication
commands.

Target-app rule and file access stays inside the worker. The main agent
integrates the worker's assessment and evidence references when it returns.

**Verification:** the audit ran inside the app's dispatched worker against its
real rule sources; its report explains the assessment and carries evidence
references; the main agent did not load the target app's files.
