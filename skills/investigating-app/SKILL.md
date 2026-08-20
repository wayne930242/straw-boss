---
name: investigating-app
description: Use when the user wants to understand how something currently works or is structured, scoped to one of the project's managed apps, with no rule violation or reported failure in question, e.g. "how does X work here", "understand how Y is implemented" — not for auditing against rules (inspecting-app), diagnosing a reported failure (troubleshooting-app), or implementing a fix (`boss-say`).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework this skill operates under — not redefined here.

Resolve the app, decide the execution tier (`boss-say`'s Task 1 — a plain subagent running your own `investigating` skill, or a dispatched agent rooted in the app), then let the actual research run. This skill doesn't reimplement investigation methodology either way.

## Task 1: Resolve the app

Invoke `work-on` now. Do not proceed without the target app.

- If `work-on` asked a clarifying question (an ambiguous name matching more than one app's `match` phrases) or found the request out of the project's managed-app scope, stop here and surface that to the user — don't guess an app to keep moving.
- If `work-on` named more than one app, treat Task 2 as running once per app rather than picking one arbitrarily; each app's research is independent.

**Verification:** the target app(s) are established before Task 2, or you've surfaced `work-on`'s clarifying question / out-of-scope result instead of proceeding.

## Task 2: Decide the tier, then hand off

Apply `boss-say`'s execution-tier judgment (its Task 1), per app: does this research need the app's own harness, or is your own global `investigating` skill, run right here, enough?

- **Solo:** invoke your `investigating` skill directly in this session (once per resolved app if `work-on` named more than one), giving it the resolved app's directory as known context.
- **Dispatch:** send it through `dispatching-work` as a worker rooted in the app's directory. The worker decides for itself whether to run an app-local research skill or your global `investigating` skill — that's the worker's call, not something to dictate in the dispatch instruction. The dispatch instruction still states the `notifying-main-agent` pointer (main-agent reachability for this dispatch's mode), the terminal-state record on `done`/`failed` (`report-task-status.py --instruction-path <path> --status <done|failed> --note "<summary>"`), and the required `SendMessage` push — same as any other dispatch, not something to skip because the work is read-only — `dispatching-work`'s Task 3 assembles this.

Either way, do not run a parallel or simplified investigation yourself instead of handing off to the real methodology.

**Verification:** the research ran against the app's actual current code, not a summary of it; the tier was judged, not defaulted to "always solo" because this is a read.

## Red Flags

- "I already know how this works, skip investigating" — no, tracing the actual current behavior is the point, not a recollection of it.
- "work-on asked a clarifying question, I'll just pick the more likely app" — no, surface the question, don't guess.
