---
name: troubleshooting-app
description: Use when something is broken and the cause is unknown, scoped to one of the project's managed apps, e.g. "X is failing", "500 in production for <app>" — not for a known task with a clear fix already in mind (shipping-task), a rule/convention audit (inspecting-app), or open-ended research into current behavior with no reported failure (investigating-app).
---

## Overview

Diagnosis only, read-only, no worktree opened yet, no dispatch yet — the cause is unknown, so there's nothing to branch for and nothing to dispatch. Diagnosis is read-only and stays in this session; once root cause is known, hand off to `shipping-task` for the actual fix, which dispatches.

## Task 1: Resolve the app

Invoke `work-on` now. Even for a live incident, you need the target app before digging in.

**Verification:** the target app is established before Task 2.

## Task 2: App-code or infrastructure?

Before debugging application code, rule out an infrastructure cause: deployment failure, orchestrator/job state, DB connectivity, config/secret drift. Symptoms like "works locally, fails in an environment", "worked yesterday, no code changed", or "500 with no recent deploy to this app" point at infrastructure, not code.

- **Looks infra-level:** hand off to this project's infrastructure/ops skill or team if one exists; otherwise tell the user plainly that this looks infrastructure-level and stop — don't debug application code for a problem that isn't in the code.
- **Looks app-level, or infra is ruled out:** continue to Task 3.

**Verification:** you can state which side the evidence points to, and why, before choosing a diagnosis path.

## Task 3: Diagnose

Read-only: reproduce, isolate, trace to a root cause using the app's own code, logs, and tests. Do not fix anything here — this task ends at "here's the root cause," not at a patch.

**Verification:** you can state a specific root cause (not just a symptom) or that you've exhausted read-only diagnosis and need to say so explicitly.

## Task 4: Hand off to the fix

Once root cause is known, tell the user and hand off to `shipping-task` for the actual fix — don't start editing files in the current, non-worktree checkout.

**Verification:** any code change happens through `shipping-task`'s worktree flow, not inline here.

## Red Flags

- "It's probably infra, I'll just say that without checking" — Task 2's verification requires stated evidence, not a guess.
- "I found the cause, let me just fix it now" — no, see Task 4. Diagnosis and fix are different skills for a reason: the fix needs a worktree and review gate.
- "Small fix, I'll edit directly instead of going through shipping-task" — no, every code change goes through the worktree flow.
