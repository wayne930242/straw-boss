---
name: work-on
description: Determines which of the project's managed apps a request belongs to. Use when straw-boss's other skills (boss-say and the shipping-task lifecycle it drives, inspecting-app, investigating-app, troubleshooting-app) need to resolve their target app as a shared first step, or when you just need to know which app a request belongs to without starting one of those flows.
---

## Overview

See `docs/roles.md` for the cast of characters and the authority framework this skill operates under — not redefined here.

App resolution and dispatch: figure out which app a request belongs to, then hand the actual work to a session rooted in that app's own directory instead of working on it here. Does not develop the fix or feature itself.

Apps' own `.claude/rules/*.md`, `.claude/skills/`, and `.claude/settings.json` hooks only load fully for a session actually rooted in that app's directory — a session working from the project root never sees an app's own skills or hooks, even though path-scoped rules and nested `CLAUDE.md` do reach it reactively. Dispatching to a session that lives in the target app closes that gap instead of working around it with a hand-maintained summary.

Locate the config with `git rev-parse --show-toplevel` from the current working directory, then read `<repo-root>/.claude/straw-boss/apps.json` — never assume the current directory is the repo root, and never search upward by hand.

**If it doesn't exist, that's not a hard stop — `init` is a convenience, not a precondition.** See Task 1's no-config handling below.

## Task 1: Resolve the target app

**No `apps.json` at all:** don't block on this — check whether the repo itself reads as single-app (no `apps/`/`packages/`/`services/`-style directory holding more than one independent codebase at the repo root). If it does, treat the repo root itself as the one implicit app — name it from its `package.json` (or equivalent manifest) or, failing that, the repo root's own directory basename; `dir` is the repo root. Proceed with the rest of this skill exactly as if that were the sole `apps.json` entry. Mention once, briefly, that running `init` is available if they want to customize git-lifecycle behavior, local-only files, etc. — but never require it first. If the repo structure genuinely looks like a monorepo instead (more than one plausible app directory) and there's no config to say which is which, that's real ambiguity, not something to guess through — ask the user which directory this specific request targets, or suggest `init` if they'd rather configure it once than get asked every time.

**Exactly one non-redirect app configured:** that's always the target — skip matching entirely, don't ask. straw-boss's dispatch model (worktree isolation, authorization-gated git lifecycle, watchable/background execution) is the point even for a single-app repo; routing across apps is an extra capability for monorepos, not a precondition for using the rest of this plugin.

**More than one:** build a routing table from `apps.json`: one row per entry, `name` + `match` phrases → `dir`. Skip entries with `redirectTo` set — those are legacy sources, handled in Task 2. Match the request against this table. If it clearly names or implies one row, that's the target — no need to ask.

If the request clearly spans more than one app, name every app it touches — don't force a single answer. Each app is routed, gated, and later shipped independently; `shipping-task` runs them as separate per-app worktree/MR/review cycles, not one blended change.

In the multi-app case, if the request doesn't match any row and isn't infrastructure/read-only (see Out of scope), say plainly that it falls outside the project's managed-app scope rather than guessing. This branch is unreachable in the single-app case — with exactly one app configured, every request resolves to it.

**Verification:** you can name the exact target directory (or directories), or you've asked a clarifying question because the name was ambiguous, or you've stated the request is out of scope.

## Task 2: Apply the legacy redirect

If the target resolved to an entry with `redirectTo` set, redirect to the named app. This is about where *new* work belongs — it does not apply to auditing code that already exists in the legacy app. Surface the entry's `note` if one is set (e.g. an app that doesn't read as deprecated, so there's a real risk of mistakenly starting work there because it looks maintained). Tell the user which active app you're routing to, so they can veto it for a true compat-only fix. If Task 1 didn't resolve to a `redirectTo` entry, this is a no-op — move on.

**Verification:** the final target is never a `redirectTo` entry unless the user explicitly overrides after being told; either way you stated the final target out loud.

## Task 3: Cross-app coordination — reuse existing precedent

If the request touches more than one app, check each pair against the resolved apps' `crossAppSkills` entries. When one exists for the pair, point to it explicitly — don't design a parallel flow. When none exists for a pair, there's no shortcut: route each app's change as its own task through this same cycle, owning/data-holding app first, dispatched independently per Task 5. No-op if the request resolved to exactly one app.

**Verification:** a multi-app request with a configured `crossAppSkills` pointer names that skill explicitly rather than describing an ad-hoc flow.

## Task 4: Decompose into a plan, if the request needs one

Only for implementation work that resolved to more than one task — either multiple apps, or multiple sequential phases within one app. A request that resolves to exactly one task skips this task entirely; go straight to Task 5.

Invoke `grilling` (or this project's equivalent decomposition-confirmation skill) to confirm the decomposition and every dependency edge with the user — one task at a time, do not silently assume how the pieces relate. Once confirmed, write `~/.straw-boss/plans/<plan-slug>/plan.json` (task list, dependency graph, high-level per-task description — not a detailed spec) and create the empty `~/.straw-boss/plans/<plan-slug>/status/` and `~/.straw-boss/plans/<plan-slug>/artifacts/` directories. Each dispatched agent applies its target app's own development and SDD route only after entering that app; Straw Boss does not pre-shape or persist that contract. See `dispatching-work`'s `references/plan-mechanics.md` for the exact schema, including the "Cross-task artifacts" convention for how a dependent task gets at its prerequisite's real output — read it, don't reconstruct it from memory.

**Verification:** a multi-task request has a confirmed-with-the-user dependency graph before `plan.json` is written; a single-task request never creates a plan.

## Task 5: Hand off

This task's job ends at naming the resolved app(s) (and, if Task 4 ran, the plan) — it does not call `dispatching-work` itself and does not decide whether to dispatch. That call — a plain subagent versus a dispatched agent rooted in the app — is `boss-say`'s execution-tier triage (its Task 1), made per item regardless of whether the work is implementation, audit, research, or diagnosis; it is never fixed by this skill or by which caller invoked it. The caller (the specialist skill that invoked this, after applying `boss-say`'s tier call) assembles the actual task description(s) and invokes `dispatching-work` if the tier call landed on dispatch — with the plan when Task 4 produced one, or a single instruction otherwise. The dispatched instruction carries the user's intent and tells the agent to follow the target app's own development route after entering it; Straw Boss does not select or run that route itself.

**Verification:** this task ends with the resolved app(s) (and plan, if any) named and control returned to the caller, not with `dispatching-work` already invoked here and not with a dispatch-or-not decision made here.

## Out of scope

- Apps not listed in `.claude/straw-boss/apps.json` — no dispatch target exists; say so. Only reachable with more than one app configured — see Task 1's single-app fast path (a missing `apps.json` in a single-app-looking repo is not this case; see Task 1's no-config handling).
- Infrastructure work outside any managed app's directory — no per-app agent system there.
- Reads/explanations that don't change code — answer inline.

## Red Flags

- "The name is close enough to one app, just pick it" — an ambiguous name (two apps with overlapping `match` phrases, or a term the project uses for more than one thing) always gets confirmed, never guessed.
- "It's legacy but the user probably wants it fixed there" — redirect and say so; let the user override explicitly.
- "A configured cross-app skill exists but describing the flow myself is simpler" — no, name the skill explicitly.
- "It's basically all one change, route as a single app" — a multi-app request gets every app named and dispatched separately.
- "The decomposition is obvious, skip grilling and just write the plan" — no, see Task 4: the user confirms the breakdown and every dependency edge before `plan.json` is written, every time.
- "No `apps.json`, stop and tell the user to run `init` first" — no, only for a repo that genuinely reads as a monorepo; a single-app-looking repo gets an implicit app and proceeds, per Task 1.
- "No `apps.json` and the repo has an `apps/` directory, just guess which one" — no, that's real ambiguity; ask, or suggest `init`.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/init/references/apps-config-schema.md` — exact `apps.json` field names and shapes.
