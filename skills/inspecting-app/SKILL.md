---
name: inspecting-app
description: Use when the user wants to check or audit something against existing rules or conventions, scoped to one of the project's managed apps, e.g. "audit this module", "check if X follows the rules" — not for open-ended research into how something currently behaves with no rule in question (investigating-app), diagnosing a reported failure (troubleshooting-app), or implementing a fix (`boss-say`).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework this skill operates under — not redefined here.

Resolve the app, choose the smallest sufficient loop through `choosing-graph`, and assess it against real rule sources. This skill supplies the app boundary; the selected audit skill supplies the method.

## Task 1: Resolve the app

Invoke `work-on` now. Do not proceed without the target app.

- If `work-on` asked a clarifying question (an ambiguous name matching more than one app's `match` phrases) or found the request out of the project's managed-app scope, stop here and surface that to the user — don't guess an app to keep moving.
- If `work-on` named more than one app, treat Task 2 as running once per app rather than picking one arbitrarily; each app's audit is independent.

**Verification:** the target app(s) are established before Task 2, or you've surfaced `work-on`'s clarifying question / out-of-scope result instead of proceeding.

## Task 2: Run an evidence-bearing audit

For a bounded single-loop, continue in the current agent with the app's instructions loaded. Use fan-out for clear independent branches, or `dispatching-work` when the audit benefits from a separate durable workroom. A confirmed lower-tier work route may carry a bounded audit.

Frame the audit around the applicable rule, observed behavior, and consequence. Require evidence references to the exact rule and implementation, test, log, or artifact. These references are what this work's anchor attacks; with no operable artifact, adversarial-review is the reality anchor for the finished assessment.

**Verification:** the evidence-backed assessment explains the result, cites both rule and observed evidence, and records its anchor disposition.
