---
name: investigating-app
description: Resolves the app and gate for a research request scoped to one of the project's managed apps, then hands off to the investigating skill. Use when the user wants to understand how something currently works or is structured, with no rule violation or reported failure in question, e.g. "how does X work here", "understand how Y is implemented" — not for auditing against rules (inspecting-app), diagnosing a reported failure (troubleshooting-app), or implementing a fix (shipping-task).
---

## Overview

Thin wrapper: resolve the app, then let the general-purpose `investigating` skill (not part of straw-boss — this hands off to whatever research skill is already in your own setup) do the actual research. This skill doesn't reimplement investigation methodology, and doesn't dispatch: research is a read-only activity that doesn't need a session actually rooted in the app, so this stays in the current session.

## Task 1: Resolve the app

Invoke `work-on` now. Do not proceed without the target app.

- If `work-on` asked a clarifying question (an ambiguous name matching more than one app's `match` phrases) or found the request out of the project's managed-app scope, stop here and surface that to the user — don't guess an app to keep moving.
- If `work-on` named more than one app, treat Task 2 as running once per app rather than picking one arbitrarily; each app's research is independent.

**Verification:** the target app(s) are established before Task 2, or you've surfaced `work-on`'s clarifying question / out-of-scope result instead of proceeding.

## Task 2: Hand off

Invoke your `investigating` skill for the actual research (once per resolved app if `work-on` named more than one), giving it the resolved app's directory as known context. Do not run a parallel or simplified investigation yourself instead of handing off.

**Verification:** the research ran against the app's actual current code, not a summary of it.

## Red Flags

- "I already know how this works, skip investigating" — no, tracing the actual current behavior is the point, not a recollection of it.
- "work-on asked a clarifying question, I'll just pick the more likely app" — no, surface the question, don't guess.
- "This is just research, dispatch it into the app's own workspace anyway" — no, research doesn't need a session rooted there; dispatch is for work that needs the app's skills/hooks to actually load.
