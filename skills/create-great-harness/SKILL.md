---
name: create-great-harness
description: Use when init finds an app with no CLAUDE.md and no .claude/ directory at all and the user agrees to bootstrap one, or when the user directly asks to set up a minimal agent system for an app that doesn't have one yet.
---

## Overview

A lightweight agent-system bootstrap for an app that has none. `CLAUDE.md` is the only unconditional artifact. A guard hook or skill-authoring rule is included only when concrete project evidence or explicit confirmed scope calls for it.

Runs either inline (a user asked for this directly) or as a dispatched agent rooted in `<app-dir>` (`init`'s own bootstrap step dispatches it via `dispatching-work`). The dispatch instruction, when present, states that scope was already confirmed and how to report completion — Task 1 and Task 6 both branch on whether that's the case.

## Task 1: Confirm scope before writing anything

State the confirmed scope before writing: `<app-dir>/CLAUDE.md`, plus any optional hook or rule the user or dispatch instruction explicitly requested. The survey may support a recommendation for another artifact, but extending the confirmed scope remains a user-owned decision.

- **Invoked directly by a user in this session:** get explicit confirmation before proceeding — this writes into the app's own checkout, not just plugin state.
- **Invoked as a dispatched agent:** the dispatch instruction already states the scope was confirmed — that confirmation *is* `init`'s own per-app yes/skip ask. Don't ask again; there's no user in this session to answer, and re-asking just stalls a `claude -p` dispatch. State the scope for the record and proceed straight to Task 2.

**Verification:** either the user confirmed in this session or the dispatch instruction carried the confirmed scope before any file was written.

## Task 2: Survey the app for non-obvious content

Read what's actually there: `package.json`/`pyproject.toml`/`Cargo.toml`/`go.mod`/equivalent manifest, lockfile (which package manager — `bun.lock` vs `package-lock.json` vs `pnpm-lock.yaml` matters), top-level directory listing, existing README if short. Filter everything through one question: **can a fresh Claude session derive this from reading the code, the manifest, or running `ls`?** If yes, it doesn't belong in `CLAUDE.md`.

Look specifically for non-default tooling (`bun` rather than the ecosystem default, a custom build/test script), the actual build/test/dev commands, and documented project-specific risks that could justify an optional guard or rule.

**If nothing non-obvious turns up** (a fully idiomatic, default-tooling setup):
say so plainly. A near-empty `CLAUDE.md` is a valid evidence-backed output.

**Verification:** every fact that ends up in `CLAUDE.md` (Task 3) traces to something read here, not to general knowledge about the language/framework.

## Task 3: Write CLAUDE.md

Use up to three relevant sections: **Role** (what this app is), **Scope** (what is in or out when that boundary is non-obvious), and **Standards** (the non-default commands or conventions Task 2 found). Omit empty sections. Keep the file concise by removing material a fresh session can derive from the manifest, repository layout, or existing focused documentation.

Every `MUST`/`NEVER` line needs a concrete reason, not aspiration — "use `bun`, not `npm`" is fine; "write clean code" is not.

**Verification:** every retained instruction is non-obvious, evidence-backed, and useful to future work in this app; report the final line count without imposing an arbitrary cap.

## Task 4: Construct an evidence-backed guard hook, when scoped

Run this task only when the confirmed scope names a guard, or Task 2 finds an app-specific irreversible risk already documented or enforced by the project and the user confirms adding a guard. A dispatched worker reports a newly discovered recommendation for later confirmation instead of expanding its own write scope.

Follow this protocol in order — an unverified hook that silently doesn't fire is worse than no hook:

1. **Dedup check.** Read `<app-dir>/.claude/settings.json` if it exists. If a hook already covers the same event+matcher:
   - **Invoked directly by a user in this session:** tell them and ask whether to keep, replace, or add alongside — don't silently double up.
   - **Invoked as a dispatched agent:** record the conflict for Task 6 and leave the existing configuration unchanged.
2. **Construct the raw command** — a `PreToolUse` hook on `Bash`, matching the destructive pattern (e.g. `git push --force`/`git push -f` to the primary branch, or `git reset --hard`) and returning a blocking decision. No `|| true`, no stderr suppression yet — that comes after the pipe-test passes.
3. **Pipe-test it** with a synthesized stdin payload matching the real hook-input shape (`{"tool_name":"Bash","tool_input":{"command":"<the exact destructive command this should block>"}}`) piped directly into the constructed command. A blocking `PreToolUse` hook signals via its **output**, not its exit code or any side effect — confirm the blocking case's stdout actually contains a deny decision (`hookSpecificOutput.permissionDecision: "deny"`, or the command exits 2 per the exit-code contract, whichever this hook uses). Also pipe-test one command it should **not** block (e.g. a plain `git push`), and confirm that case's output has no deny decision — an exit-0 "it ran without erroring" is not evidence either direction on its own.
4. **Merge into `<app-dir>/.claude/settings.json`** — read-then-merge, never overwrite existing hooks/permissions/settings already in the file. Create the file (and `.claude/`) only if neither exists.
5. **Validate:** `jq -e '.hooks.PreToolUse[] | select(.matcher == "Bash") | .hooks[] | select(.type == "command") | .command' <app-dir>/.claude/settings.json` — exits 0 and prints the command, or the write is wrong.
6. **Note the watcher caveat** for Task 6's report: a hook added to a `.claude/` directory that didn't exist when the current session started won't fire until `/hooks` is opened once or the session restarts — this skill cannot trigger that itself.

**Verification:** when Task 4 was in scope, the hook was pipe-tested against both a blocking and a non-blocking case before writing and `jq -e` confirms the merged JSON; a conflict or newly discovered recommendation is reported without an unconfirmed write.

## Task 5: Write a skill-authoring rule, when scoped

Run this task only when the confirmed scope explicitly requests skill-authoring guidance or the app already has an app-owned skill system whose current rules establish that need. Resolve the current provider specification at execution time:

1. **Resolve both component pages from the live index**, not memory:
   ```
   WebFetch
     url: https://code.claude.com/docs/llms.txt
     prompt: "Return all entries related to: skill, rule. Include reference and guide URLs for each. Quote the URLs verbatim."
   ```
2. **Fetch each resolved reference page** (frontmatter/schema, not the usage guide):
   - Skill reference → `WebFetch` prompt: "Extract frontmatter fields, naming/description conventions, and discovery mechanics. Return verbatim excerpts, not a summary."
   - Rule reference → `WebFetch` prompt: "Extract frontmatter fields and the path-scoping mechanism — how a rule auto-injects only for matching files. Return verbatim excerpts, not a summary."

   On a non-2xx or empty result from either fetch, re-fetch `llms.txt` once (bypassing cache if possible) to confirm the URL didn't move. If it still fails, skip this task, tell whoever's listening why (inline or via Task 6's reporting channel), and don't write a rule guessed from memory instead.
3. **Write `<app-dir>/.claude/rules/skill-writing.md`** using the rule frontmatter/path-scoping the second fetch just returned — scope it to `.claude/skills/**` so it only auto-injects when someone's actually touching a skill — with the skill-writing content distilled from the first fetch, quoted or closely paraphrased from what was actually fetched, not general knowledge. Note the source URL and fetch date in the file so a later reader knows how stale it might be.

**Verification:** both the file's own frontmatter/scoping and its skill-writing content trace to this task's live fetches, not memory; the rule auto-injects only under `.claude/skills/**`, never globally; a failed fetch was reported, never papered over with a guessed rule.

## Task 6: Report

State what now exists: `CLAUDE.md`'s line count and section summary, plus each confirmed optional artifact actually written. Report evidence-backed recommendations, conflicts, fetch failures, and any `/hooks`-or-restart caveat separately from completed writes.

- **Invoked directly by a user in this session:** report inline, in this conversation.
- **Invoked as a dispatched agent:** state it as this turn's own final text output and run `report-task-status.py --instruction-path <path> --status done --note "<one-line summary>"`. That command writes durable state before notifying the recorded main-agent herdr pane. Follow `notifying-main-agent` only for a valid Claude-to-Claude fallback if herdr is unavailable or fails.

**Verification:** the report distinguishes written artifacts from recommendations; under dispatch, the shared terminal-status command succeeded or its preserved-status notification failure was surfaced.

## References

None outside this plugin, deliberately — this skill doesn't depend on any other plugin being installed. Task 5's `WebFetch` calls go to a public URL (`code.claude.com`), not to another plugin's skill — that keeps the same zero-plugin-dependency guarantee while still pulling live spec content instead of stale memory.
