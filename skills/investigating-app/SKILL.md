---
name: investigating-app
description: Use when the user wants to understand how something currently works or is structured, scoped to one of the project's managed apps, with no rule violation or reported failure in question, e.g. "how does X work here", "understand how Y is implemented" — not for auditing against rules (inspecting-app), diagnosing a reported failure (troubleshooting-app), or implementing a fix (`boss-say`).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework this skill operates under — not redefined here.

Resolve the app, then dispatch the actual research into it. Managed-app
current-state research always dispatches so the app's agent system loads only in
the worker session, not the main agent's coordination context. This skill does
not reimplement investigation methodology.

## Task 1: Resolve the app

Invoke `work-on` now. Do not proceed without the target app.

- If `work-on` asked a clarifying question (an ambiguous name matching more than one app's `match` phrases) or found the request out of the project's managed-app scope, stop here and surface that to the user — don't guess an app to keep moving.
- If `work-on` named more than one app, treat Task 2 as running once per app rather than picking one arbitrarily; each app's research is independent.

**Verification:** the target app(s) are established before Task 2, or you've surfaced `work-on`'s clarifying question / out-of-scope result instead of proceeding.

## Task 2: Dispatch an evidence-bearing investigation

Send each resolved app through `dispatching-work` as a worker rooted in that
app's directory. A bounded investigation may resolve to a confirmed lower-tier
work route, such as Haiku or a lower-tier Codex model; do not override the
project's confirmed route with an invented model choice.

Frame the task around what current behavior, structure, mechanism, cause, or
impact the worker must explain. Require evidence references such as file and
line locations, tests, logs, commands, or generated artifacts. The deliverable
is an explanatory, evidence-backed account of the finding. The worker decides
whether to run an app-local research skill or global
`investigating`; the generated contract supplies instruction-keyed status and
communication commands.

Target-app file access stays inside the worker. The main agent integrates the
worker's conclusion and evidence references when it returns.

**Verification:** the research ran inside the app's dispatched worker; its report
explains the finding and carries evidence references; the main agent did not load
the target app's files.
