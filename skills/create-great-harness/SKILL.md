---
name: create-great-harness
description: Use when init finds an app with no CLAUDE.md and no .claude/ directory at all and the user agrees to bootstrap one, or when the user directly asks to set up a minimal agent system for an app that doesn't have one yet.
---

## Overview

A lightweight agent-system bootstrap for an app that has none: a short `CLAUDE.md` (Role/Scope/Standards, non-obvious content only) plus one verified guard hook for the single most common destructive footgun. Not a scaffold of empty `.claude/skills/`/`.claude/rules/` directories — those earn their place only once there's real content to put in them.

## Task 1: Confirm scope before writing anything

State exactly what will be created: `<app-dir>/CLAUDE.md` and one guard hook in `<app-dir>/.claude/settings.json`. Get explicit confirmation — this writes into the app's own checkout, not just plugin state.

**Verification:** the user confirmed before Task 2 starts reading files or Task 4 starts writing.

## Task 2: Survey the app for non-obvious content

Read what's actually there: `package.json`/`pyproject.toml`/`Cargo.toml`/`go.mod`/equivalent manifest, lockfile (which package manager — `bun.lock` vs `package-lock.json` vs `pnpm-lock.yaml` matters), top-level directory listing, existing README if short. Filter everything through one question: **can a fresh Claude session derive this from reading the code, the manifest, or running `ls`?** If yes, it doesn't belong in `CLAUDE.md`.

Look specifically for: non-default tooling (`bun` not `npm`, `uv` not `pip`, a custom build/test script), the actual build/test/dev commands (from the manifest's scripts, not assumed), and one thing worth a guard hook (see Task 4).

**If nothing non-obvious turns up** (a fully idiomatic, default-tooling setup): say so plainly. A near-empty `CLAUDE.md` — or one that's mostly Task 4's hook and a one-line Role — is the correct output, not a sign to pad it with generic advice.

**Verification:** every fact that ends up in `CLAUDE.md` (Task 3) traces to something read here, not to general knowledge about the language/framework.

## Task 3: Write CLAUDE.md

Three sections only — **Role** (what this app is, one or two lines), **Scope** (what's in/out of it, if non-obvious), **Standards** (the actual non-default commands/conventions Task 2 found). No Workflow, no Completion criteria, no architecture diagram, no directory listing — those belong in skills, or are derivable by `ls`. Target under 100 lines; there is no floor.

Every `MUST`/`NEVER` line needs a concrete reason, not aspiration — "use `bun`, not `npm`" is fine; "write clean code" is not.

**Verification:** every line is something Task 2 actually found, not restated from a README/manifest/package.json; total length is stated and under 100 lines, or the overage is justified out loud.

## Task 4: Construct one guard hook

**Default: block a force-push or hard-reset on the app's primary branch** — universally applicable regardless of stack, and the single most common irreversible-mistake footgun. Substitute a different single guard only when Task 2's survey surfaced something equally simple and more obviously relevant (e.g. a migrations/seed directory an `rm -rf` could wipe) — never write more than one hook, and never chain unrelated guards into it.

Follow this protocol in order — an unverified hook that silently doesn't fire is worse than no hook:

1. **Dedup check.** Read `<app-dir>/.claude/settings.json` if it exists. If a hook already covers the same event+matcher, tell the user and ask whether to keep, replace, or add alongside — don't silently double up.
2. **Construct the raw command** — a `PreToolUse` hook on `Bash`, matching the destructive pattern (e.g. `git push --force`/`git push -f` to the primary branch, or `git reset --hard`) and returning a blocking decision. No `|| true`, no stderr suppression yet — that comes after the pipe-test passes.
3. **Pipe-test it** with a synthesized stdin payload matching the real hook-input shape (`{"tool_name":"Bash","tool_input":{"command":"<the exact destructive command this should block>"}}`) piped directly into the constructed command. A blocking `PreToolUse` hook signals via its **output**, not its exit code or any side effect — confirm the blocking case's stdout actually contains a deny decision (`hookSpecificOutput.permissionDecision: "deny"`, or the command exits 2 per the exit-code contract, whichever this hook uses). Also pipe-test one command it should **not** block (e.g. a plain `git push`), and confirm that case's output has no deny decision — an exit-0 "it ran without erroring" is not evidence either direction on its own.
4. **Merge into `<app-dir>/.claude/settings.json`** — read-then-merge, never overwrite existing hooks/permissions/settings already in the file. Create the file (and `.claude/`) only if neither exists.
5. **Validate:** `jq -e '.hooks.PreToolUse[] | select(.matcher == "Bash") | .hooks[] | select(.type == "command") | .command' <app-dir>/.claude/settings.json` — exits 0 and prints the command, or the write is wrong.
6. **State the watcher caveat** to the user: a hook added to a `.claude/` directory that didn't exist when the current session started won't fire until `/hooks` is opened once or the session restarts — this skill cannot trigger that itself.

**Verification:** the hook was pipe-tested against both a blocking and a non-blocking case before being written; `jq -e` confirms the written JSON; the watcher caveat was stated, not assumed away.

## Task 5: Report

Tell the user what now exists: `CLAUDE.md`'s line count and section summary, the guard hook's exact trigger condition and file location, and the `/hooks`-or-restart caveat if it applies. Hand back to `init`, which continues checking the remaining apps.

**Verification:** the user knows both what was written and what to do (if anything) to make the hook take effect immediately.

## Red Flags

- "No non-obvious tooling found, add some general best-practices anyway to look complete" — no, Task 2/3: a short or near-empty `CLAUDE.md` is correct when nothing non-obvious exists.
- "Just CLAUDE.md is fine, skip the hook" — no, this skill's reason to exist beyond writing a file is that prose is roughly-compliance-only; a destructive-action rule needs the hook.
- "Scaffold empty `.claude/skills/`/`.claude/rules/` directories too, more structure looks more thorough" — no, out of scope for this skill; they earn their place once there's real content.
- "Write the hook and move on, pipe-testing takes an extra step" — no, Task 4 pipe-tests both a blocking and a non-blocking case before writing.
- "Exit code was 0, the pipe-test passed" — no, a blocking `PreToolUse` hook signals through its output, not its exit code; check the actual deny decision is present (blocking case) or absent (non-blocking case).
- "Chain a few guards into one hook while I'm at it" — no, one hook, the single most relevant guard; more can be added later, deliberately, not bundled in here.
- "Overwrite the existing `.claude/settings.json` wholesale" — no, Task 4 step 4: read-then-merge, always.

## References

None outside this plugin, deliberately — this skill doesn't depend on any other plugin being installed.
