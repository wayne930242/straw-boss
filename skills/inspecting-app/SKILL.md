---
name: inspecting-app
description: Use when the user wants to check or audit something against existing rules or conventions, scoped to one of the project's managed apps, e.g. "audit this module", "check if X follows the rules" — not for open-ended research into how something currently behaves with no rule in question (investigating-app), diagnosing a reported failure (troubleshooting-app), or implementing a fix (shipping-task).
---

## Overview

Thin wrapper: resolve the app, then let the general-purpose `inspecting` skill (not part of straw-boss — this hands off to whatever audit skill is already in your own setup) do the actual audit against that app's real rules. This skill doesn't reimplement audit methodology, and doesn't dispatch: reading and checking compliance don't need a session actually rooted in the app (that's only needed for skills/hooks to load, which this doesn't rely on), so this stays in the current session.

## Task 1: Resolve the app

Invoke `work-on` now. Do not proceed without the target app.

- If `work-on` asked a clarifying question (an ambiguous name matching more than one app's `match` phrases) or found the request out of the project's managed-app scope, stop here and surface that to the user — don't guess an app to keep moving.
- If `work-on` named more than one app, treat Task 2 as running once per app rather than picking one arbitrarily; each app's audit is independent.

**Verification:** the target app(s) are established before Task 2, or you've surfaced `work-on`'s clarifying question / out-of-scope result instead of proceeding.

## Task 2: Hand off

Invoke your `inspecting` skill for the actual check (once per resolved app if `work-on` named more than one), giving it the resolved app's directory as known context — it reads that app's actual `.claude/rules/`/`CLAUDE.md` itself to build its check plan; there's no condensed digest to hand it. Do not run a parallel or simplified audit yourself instead of handing off.

**Verification:** the audit ran against the app's real rule source, not a summary of it.

## Red Flags

- "I'll just review it myself inline instead of invoking inspecting" — no, that's a different, less thorough process than what this skill exists to trigger.
- "work-on asked a clarifying question, I'll just pick the more likely app" — no, surface the question, don't guess.
- "This is a compliance check, dispatch it into the app's own workspace" — no, reading and checking don't need a session rooted there; dispatch is for work that needs the app's skills/hooks to actually load.
