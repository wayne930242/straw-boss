---
name: work-on
description: Determines which of the project's managed apps a request belongs to. Use when straw-boss's other skills (boss-say and the shipping-task lifecycle it drives, inspecting-app, investigating-app, troubleshooting-app) need to resolve their target app as a shared first step, or when you just need to know which app a request belongs to without starting one of those flows.
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework this skill operates under — not redefined here.

App resolution: identify the checkout and return it to the caller. The caller's chosen coordination graph decides whether the current agent works there or opens a separate app-rooted workroom.

An agent working in the app loads its own instructions before acting. A separate workroom is useful when the caller needs the app's full session harness or a durable interactive lifecycle.

Locate the config with `git rev-parse --show-toplevel` from the current working directory, then read `<repo-root>/.claude/straw-boss/apps.json` — never assume the current directory is the repo root, and never search upward by hand.

**If it doesn't exist, that's not a hard stop — `init` is a convenience, not a precondition.** See Task 1's no-config handling below.

## Task 1: Resolve the target app

**No `apps.json` at all:** don't block on this — check whether the repo itself reads as single-app (no `apps/`/`packages/`/`services/`-style directory holding more than one independent codebase at the repo root). If it does, treat the repo root itself as the one implicit app — name it from its `package.json` (or equivalent manifest) or, failing that, the repo root's own directory basename; `dir` is the repo root. Proceed with the rest of this skill exactly as if that were the sole `apps.json` entry. Mention once, briefly, that running `init` is available if they want to customize git-lifecycle behavior, local-only files, etc. — but never require it first. If the repo structure genuinely looks like a monorepo instead (more than one plausible app directory) and there's no config to say which is which, that's real ambiguity, not something to guess through — ask the user which directory this specific request targets, or suggest `init` if they'd rather configure it once than get asked every time.

**Exactly one non-redirect app configured:** use it as the target unless the
request is explicitly outside that app, such as infrastructure owned elsewhere
or a self-contained external lookup. In that case, return the out-of-scope
classification to the caller. Otherwise skip matching and proceed.

**More than one:** build a routing table from `apps.json`: one row per entry, `name` + `match` phrases → `dir`. Skip entries with `redirectTo` set — those are legacy sources, handled in Task 2. Match the request against this table. If it clearly names or implies one row, that's the target — no need to ask.

If the request clearly spans more than one app, name every app it touches — don't force a single answer. Each app is routed, gated, and later shipped independently; `shipping-task` runs them as separate per-app worktree/MR/review cycles, not one blended change.

In the multi-app case, if the request doesn't match any row and is explicitly
outside managed-app work (see Out of scope), say plainly that it falls outside
the project's managed-app scope. An unmatched app-related request is clarified
with the user.

**Verification:** you can name the exact target directory (or directories), or you've asked a clarifying question because the name was ambiguous, or you've stated the request is out of scope.

## Task 2: Apply the legacy redirect

If the target resolved to an entry with `redirectTo` set, redirect to the named app. This is about where *new* work belongs — it does not apply to auditing code that already exists in the legacy app. Surface the entry's `note` if one is set (e.g. an app that doesn't read as deprecated, so there's a real risk of mistakenly starting work there because it looks maintained). Tell the user which active app you're routing to, so they can veto it for a true compat-only fix. If Task 1 didn't resolve to a `redirectTo` entry, this is a no-op — move on.

**Verification:** the final target is never a `redirectTo` entry unless the user explicitly overrides after being told; either way you stated the final target out loud.

## Task 3: Cross-app coordination — reuse existing precedent

If the request touches more than one app, check each pair against the resolved
apps' `crossAppSkills` entries. When one exists for the pair, point to it
explicitly. Otherwise represent each app's work as its own task. Task 4 confirms
any ordering or dependency relationship with the user; app ownership alone does
not establish one. This is a no-op for a single-app request.

**Verification:** a multi-app request with a configured `crossAppSkills` pointer names that skill explicitly rather than describing an ad-hoc flow.

## Task 4: Decompose into a plan, if the request needs one

Only for implementation work that resolved to more than one task — either multiple apps, or multiple sequential phases within one app. A request that resolves to exactly one task skips this task entirely; go straight to Task 5.

Invoke `grilling` (or this project's equivalent decomposition-confirmation skill) to confirm the decomposition and every dependency edge with the user — one task at a time, do not silently assume how the pieces relate. Once confirmed, write `~/.straw-boss/plans/<plan-slug>/plan.json` (task list, dependency graph, high-level per-task description — not a detailed spec) and create the empty `~/.straw-boss/plans/<plan-slug>/status/` and `~/.straw-boss/plans/<plan-slug>/artifacts/` directories. Each dispatched agent applies its target app's own development and SDD route only after entering that app; Straw Boss does not pre-shape or persist that contract. See `dispatching-work`'s `references/plan-mechanics.md` for the exact schema, including the "Cross-task artifacts" convention for how a dependent task gets at its prerequisite's real output — read it, don't reconstruct it from memory.

**Verification:** a multi-task request has a confirmed-with-the-user dependency graph before `plan.json` is written; a single-task request never creates a plan.

## Task 5: Return the resolution

This skill returns the resolved app to its caller, including its directory and any multi-task plan. The caller applies `choosing-graph`: a bounded single-loop may continue in the current agent, while work that benefits from an independent app-rooted session continues through `dispatching-work`. Either route loads the target app's instructions before doing target-app work.

**Verification:** this task returns the resolved app(s) and plan, if any, without choosing the caller's execution tier.

## Out of scope

- Apps not listed in `.claude/straw-boss/apps.json` — no dispatch target exists; say so. Only reachable with more than one app configured — see Task 1's single-app fast path (a missing `apps.json` in a single-app-looking repo is not this case; see Task 1's no-config handling).
- Infrastructure work outside any managed app's directory — no per-app agent system there.
- Self-contained or external reads that need no managed-app files — no app
  dispatch target is required.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md` — exact `apps.json` field names and shapes.
