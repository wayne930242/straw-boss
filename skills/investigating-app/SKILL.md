---
name: investigating-app
description: Use when the user wants to understand how something currently works or is structured, scoped to one of the project's managed apps, with no rule violation or reported failure in question, e.g. "how does X work here", "understand how Y is implemented" — not for auditing against rules (inspecting-app), diagnosing a reported failure (troubleshooting-app), or implementing a fix (`boss-say`).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework this skill operates under — not redefined here.

Resolve the app, choose the smallest sufficient loop through `choosing-graph`, and produce an evidence-backed explanation. This skill supplies the app boundary; the selected research skill supplies the method.

## Task 1: Resolve the app

Invoke `work-on` now. Do not proceed without the target app.

- If `work-on` asked a clarifying question (an ambiguous name matching more than one app's `match` phrases) or found the request out of the project's managed-app scope, stop here and surface that to the user — don't guess an app to keep moving.
- If `work-on` named more than one app, treat Task 2 as running once per app rather than picking one arbitrarily; each app's research is independent.

**Verification:** the target app(s) are established before Task 2, or you've surfaced `work-on`'s clarifying question / out-of-scope result instead of proceeding.

## Task 2: Run an evidence-bearing investigation

For a bounded single-loop, continue in the current agent with the app's instructions loaded. Use fan-out for clear independent branches, or `dispatching-work` when the research benefits from a separate durable workroom. A confirmed lower-tier work route may carry bounded fact gathering.

Frame the work around the behavior, structure, mechanism, cause, or impact to explain. Require file/line, test, log, command, or artifact evidence references. These references are what this work's anchor attacks; with no operable artifact, adversarial-review is the reality anchor for the finished account.

**Verification:** the report explains the finding, cites evidence, and records its anchor disposition.
