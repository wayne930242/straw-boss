---
name: work-on
description: Use to resolve which of the project's managed apps a request belongs to.
---

## Overview

App resolution: identify the checkout and return it to the caller. This skill returns the resolved app to its caller, including its directory and any multi-task plan, without choosing the caller's execution tier. The caller applies `choosing-graph`: a bounded single-loop may continue in the current agent, while work that benefits from an independent app-rooted session continues through `dispatching-work`. Either route loads the target app's instructions before doing target-app work.

Resolve the repo root from the current directory with `git rev-parse --show-toplevel`, then run the shared read handler in `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md`. On exit 0, use the returned `config` and its source; exit 3 takes you to the no-config branch below; exit 1 means a config error to report, fix, and retry. A missing config is not a hard stop — `init` is a convenience, not a precondition.

## Task 1: Resolve the target app

**No `apps.json` at all:** which branch applies depends on how the repo itself reads.

- **Reads as single-app** (no `apps/`/`packages/`/`services/`-style directory holding more than one independent codebase at the repo root): treat the repo root itself as the one implicit app — name it from its `package.json` (or equivalent manifest) or, failing that, the repo root's own directory basename; `dir` is the repo root. Mention once, briefly, that running `init` is available if they want to customize git-lifecycle behavior, local-only files, etc. — but never require it first.
- **Reads as a monorepo** (more than one plausible app directory, and no config to say which is which): that's real ambiguity, not something to guess through — ask the user which directory this specific request targets, or suggest `init` if they'd rather configure it once than get asked every time.

**Exactly one non-redirect app configured:** use it as the target unless the request is explicitly outside that app, such as infrastructure owned elsewhere or a self-contained external lookup. In that case, return the out-of-scope classification to the caller. Otherwise skip matching and proceed.

**More than one:** build a routing table from `apps.json` — one row per entry, `name` + `match` phrases → `dir`, skipping entries with `redirectTo` set — and match the request against it.

- Clearly names or implies one row: that's the target.
- Spans more than one app: name every app it touches. Each ships independently through its own `shipping-task` cycle, so don't force a single answer.
- Matches no row and is explicitly outside managed-app work (see Out of scope): say so plainly.
- Matches no row but is app-related: clarify with the user.

**Resolved to a `redirectTo` entry:** redirect to the named app. This is about where *new* work belongs — it does not apply to auditing code that already exists in the legacy app. Surface the entry's `note` if one is set, and tell the user which active app you're routing to, so they can veto it for a true compat-only fix. The final target is never a `redirectTo` entry unless the user explicitly overrides after being told.

**Resolved to more than one app:** check each pair against the resolved apps' `crossAppSkills` entries. Where one exists for the pair, point to it explicitly; otherwise represent each app's work as its own task. App ownership alone establishes no ordering — Task 2 confirms any dependency relationship with the user.

**Verification:** you can name the exact target directory (or directories), or you've asked a clarifying question because the name was ambiguous, or you've stated the request is out of scope; the final target and any `crossAppSkills` pointer were stated out loud.

## Task 2: Decompose into a plan, if the request needs one

Only for implementation work that resolved to more than one task — either multiple apps, or multiple sequential phases within one app. A request that resolves to exactly one task skips this task entirely and returns.

Invoke `grilling` (or this project's equivalent decomposition-confirmation skill) to confirm the decomposition and every dependency edge with the user — one task at a time, do not silently assume how the pieces relate. Once confirmed:

- Write `~/.straw-boss/plans/<plan-slug>/plan.json` — task list, dependency graph, high-level per-task description, not a detailed spec.
- Create the empty `~/.straw-boss/plans/<plan-slug>/status/` and `~/.straw-boss/plans/<plan-slug>/artifacts/` directories.

Each dispatched agent applies its target app's own development and SDD route only after entering that app; Straw Boss does not pre-shape or persist that contract. See `dispatching-work`'s `references/plan-mechanics.md` for the exact schema, including the "Cross-task artifacts" convention for how a dependent task gets at its prerequisite's real output.

**Verification:** a multi-task request has a confirmed-with-the-user dependency graph before `plan.json` is written; a single-task request never creates a plan.

## Out of scope

- Apps not listed in the handler-resolved apps config — no dispatch target exists; say so. Only reachable with more than one app configured (a missing `apps.json` in a single-app-looking repo is Task 1's no-config branch, not this).
- Infrastructure work outside any managed app's directory — no per-app agent system there.
- Self-contained or external reads that need no managed-app files — no app dispatch target is required.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md` — exact `apps.json` field names and shapes.
