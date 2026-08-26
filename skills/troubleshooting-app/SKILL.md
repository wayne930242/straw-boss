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
files, or artifacts. The deliverable is a falsifiable root-cause explanation,
not a yes-or-no answer about whether one suspected cause exists. The worker
reports through `report-task-status.py --instruction-path <path> --status done
--note "<root cause>" --ref "<evidence>"`, which writes before notifying the
recorded main-agent herdr pane. It never invokes `boss-say` or dispatches anything
itself.

Do not read target-app files or reproduce the failure in the main-agent session.
Do not fix anything here: this task ends at "here's the root cause," not a patch.

**Verification:** the dispatched report states a specific root cause or an
explicitly exhausted hypothesis set, includes evidence references, and never
escalates to a fix on its own.

## Task 4: Hand off to the fix

Once root cause is known — from your own diagnosis, or a dispatched worker's completion report — tell the user and hand off to `boss-say` for the actual fix — it triages the fix (normally one item, so it routes straight to `shipping-task`) and makes its own execution-tier call for it. Don't start editing files in the current, non-worktree checkout, and don't call `shipping-task` around `boss-say`.

**Verification:** any code change is handed to `boss-say`, not made inline here.

## Red Flags

- "It's probably infra, I'll just say that without checking" — Task 2's verification requires stated evidence, not a guess.
- "I found the cause, let me just fix it now" — no, see Task 4. Diagnosis and fix are different skills for a reason: the fix needs a worktree and review gate.
- "Small fix, I'll edit directly instead of handing it to `boss-say`" — no, every code change goes back through the main agent for dispatch.
- "The fix is obviously one task, call `shipping-task` directly and skip `boss-say`" — no, dispatch triage is the main agent's, even when the answer is 'one task'.
- "The dispatched diagnosis found root cause, have it call `boss-say`/`shipping-task` itself to save a round trip" — no, a worker only runs its shared completion-status command; deciding what happens with a root cause stays with the session that dispatched it.
- "Ask whether the suspected cause exists" — no, ask the worker to explain the
  failure mechanism and return evidence that supports or falsifies the hypothesis.
