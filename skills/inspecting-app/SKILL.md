---
name: inspecting-app
description: Use when the user wants to check or audit something against existing rules or conventions, scoped to one of the project's managed apps, e.g. "audit this module", "check if X follows the rules" — not for open-ended research into how something currently behaves with no rule in question (investigating-app), diagnosing a reported failure (troubleshooting-app), or implementing a fix (`boss-say`).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework this skill operates under — not redefined here.

Resolve the app, decide the execution tier (`boss-say`'s Task 1 — a plain subagent running your own `inspecting` skill, or a dispatched agent rooted in the app), then let the actual audit run. This skill doesn't reimplement audit methodology either way.

## Task 1: Resolve the app

Invoke `work-on` now. Do not proceed without the target app.

- If `work-on` asked a clarifying question (an ambiguous name matching more than one app's `match` phrases) or found the request out of the project's managed-app scope, stop here and surface that to the user — don't guess an app to keep moving.
- If `work-on` named more than one app, treat Task 2 as running once per app rather than picking one arbitrarily; each app's audit is independent.

**Verification:** the target app(s) are established before Task 2, or you've surfaced `work-on`'s clarifying question / out-of-scope result instead of proceeding.

## Task 2: Decide the tier, then hand off

Apply `boss-say`'s execution-tier judgment (its Task 1), per app: does this audit need the app's own harness (its real `.claude/rules/`/`CLAUDE.md`, and possibly its own local audit skill), or is your own global `inspecting` skill, run right here, enough?

- **Solo:** invoke your `inspecting` skill directly in this session (once per resolved app if `work-on` named more than one), giving it the resolved app's directory as known context — it reads that app's actual rules itself to build its check plan; there's no condensed digest to hand it.
- **Dispatch:** send it through `dispatching-work` as a worker rooted in the app's directory. The worker decides for itself whether to run the app's own local audit skill or your global `inspecting` skill — that's the worker's call, not something to dictate in the dispatch instruction. The dispatch instruction still states the `notifying-main-agent` pointer (main-agent reachability for this dispatch's mode), the terminal-state record on `done`/`failed` (`report-task-status.py --instruction-path <path> --status <done|failed> --note "<summary>"`), and the required `SendMessage` push — same as any other dispatch, not something to skip because the work is read-only — `dispatching-work`'s Task 3 assembles this.

Either way, do not run a parallel or simplified audit yourself instead of handing off to the real methodology.

**Verification:** the audit ran against the app's real rule source, not a summary of it; the tier was judged, not defaulted to "always solo" because this is a read.

## Red Flags

- "I'll just review it myself inline instead of invoking inspecting" — no, that's a different, less thorough process than what this skill exists to trigger.
- "work-on asked a clarifying question, I'll just pick the more likely app" — no, surface the question, don't guess.
