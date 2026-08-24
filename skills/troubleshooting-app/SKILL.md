---
name: troubleshooting-app
description: Use when something is broken and the cause is unknown, scoped to one of the project's managed apps, e.g. "X is failing", "500 in production for <app>" — not for a known task with a clear fix already in mind (`boss-say`), a rule/convention audit (inspecting-app), or open-ended research into current behavior with no reported failure (investigating-app).
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework this skill operates under — not redefined here.

No worktree opened yet, no fix made yet — the cause is unknown, so there's nothing to branch for and nothing to patch. Diagnosis (Task 3) is read-only either way; whether it stays solo in this session or dispatches to a worker rooted in the app is `boss-say`'s execution-tier judgment. Once root cause is known, hand off to `boss-say` for the actual fix, which triages it and makes its own tier call.

## Task 1: Resolve the app

Invoke `work-on` now. Even for a live incident, you need the target app before digging in.

**Verification:** the target app is established before Task 2.

## Task 2: App-code or infrastructure?

Before debugging application code, rule out an infrastructure cause: deployment failure, orchestrator/job state, DB connectivity, config/secret drift. Symptoms like "works locally, fails in an environment", "worked yesterday, no code changed", or "500 with no recent deploy to this app" point at infrastructure, not code.

- **Looks infra-level:** hand off to this project's infrastructure/ops skill or team if one exists; otherwise tell the user plainly that this looks infrastructure-level and stop — don't debug application code for a problem that isn't in the code.
- **Looks app-level, or infra is ruled out:** continue to Task 3.

**Verification:** you can state which side the evidence points to, and why, before choosing a diagnosis path.

## Task 3: Diagnose

Apply `boss-say`'s execution-tier judgment (its Task 1): does root-causing this need the app's own harness (its logs, tests, actual code loaded in a session rooted there), or can you reproduce, isolate, and trace it well enough from here?

- **Solo:** read-only, in this session — reproduce, isolate, trace to a root cause using the app's own code, logs, and tests.
- **Dispatch:** send it through `dispatching-work` as a worker rooted in the app's directory, diagnosis only — the instruction states the task ends at a root cause, not a patch. The worker reports through `report-task-status.py --instruction-path <path> --status done --note "<root cause>"`, which writes before notifying the recorded main-agent herdr pane; a Claude worker uses `notifying-main-agent` only for routing or valid Claude-to-Claude fallback. It never invokes `boss-say` or dispatches anything itself.

Do not fix anything here — this task ends at "here's the root cause," not at a patch, on either tier.

**Verification:** you can state a specific root cause (not just a symptom) or that you've exhausted diagnosis and need to say so explicitly; a dispatched diagnosis never escalated to a fix on its own.

## Task 4: Hand off to the fix

Once root cause is known — from your own diagnosis, or a dispatched worker's completion report — tell the user and hand off to `boss-say` for the actual fix — it triages the fix (normally one item, so it routes straight to `shipping-task`) and makes its own execution-tier call for it. Don't start editing files in the current, non-worktree checkout, and don't call `shipping-task` around `boss-say`.

**Verification:** any code change is handed to `boss-say`, not made inline here.

## Red Flags

- "It's probably infra, I'll just say that without checking" — Task 2's verification requires stated evidence, not a guess.
- "I found the cause, let me just fix it now" — no, see Task 4. Diagnosis and fix are different skills for a reason: the fix needs a worktree and review gate.
- "Small fix, I'll edit directly instead of handing it to `boss-say`" — no, every code change goes back through the main agent for dispatch.
- "The fix is obviously one task, call `shipping-task` directly and skip `boss-say`" — no, dispatch triage is the main agent's, even when the answer is 'one task'.
- "The dispatched diagnosis found root cause, have it call `boss-say`/`shipping-task` itself to save a round trip" — no, a worker only runs its shared completion-status command; deciding what happens with a root cause stays with the session that dispatched it.
