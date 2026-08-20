---
name: create-great-harness
description: Use when init finds an app with no CLAUDE.md and no .claude/ directory at all and the user agrees to bootstrap one, or when the user directly asks to set up a minimal agent system for an app that doesn't have one yet.
---

## Overview

A lightweight agent-system bootstrap for an app that has none: a short `CLAUDE.md` (Role/Scope/Standards, non-obvious content only), one verified guard hook for the single most common destructive footgun, and one rule that pins future skill-authoring in this app to the current official spec rather than stale training data. Not a scaffold of empty `.claude/skills/` directories or a full rules library — those earn their place only once there's real content to put in them; the skill-authoring rule is the one exception, because it costs nothing to keep current (a live fetch, not hand-maintained prose) and every app that ever grows a `.claude/skills/` needs it from the first skill written, not retrofitted after an off-spec one already exists.

Runs either inline (a user asked for this directly) or as a dispatched agent rooted in `<app-dir>` (`init`'s own bootstrap step dispatches it via `dispatching-work`). The dispatch instruction, when present, states that scope was already confirmed and how to report completion — Task 1 and Task 6 both branch on whether that's the case.

## Task 1: Confirm scope before writing anything

State exactly what will be created: `<app-dir>/CLAUDE.md`, one guard hook in `<app-dir>/.claude/settings.json`, and one rule in `<app-dir>/.claude/rules/`.

- **Invoked directly by a user in this session:** get explicit confirmation before proceeding — this writes into the app's own checkout, not just plugin state.
- **Invoked as a dispatched agent:** the dispatch instruction already states the scope was confirmed — that confirmation *is* `init`'s own per-app yes/skip ask. Don't ask again; there's no user in this session to answer, and re-asking just stalls a `claude -p` dispatch. State the scope for the record and proceed straight to Task 2.

**Verification:** either the user confirmed in this session before Task 2/4 started, or the dispatch instruction already carried a confirmed scope — never neither.

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

1. **Dedup check.** Read `<app-dir>/.claude/settings.json` if it exists. If a hook already covers the same event+matcher:
   - **Invoked directly by a user in this session:** tell them and ask whether to keep, replace, or add alongside — don't silently double up.
   - **Invoked as a dispatched agent:** there's no one to answer that under `claude -p`. Skip writing the hook, note the conflict for Task 6's report instead, and continue to Task 5 — a stale duplicate hook is worse than one app missing this run's guard hook, and the conflict is exactly the kind of thing `init` (or the user, once told) should resolve, not something to guess past.
2. **Construct the raw command** — a `PreToolUse` hook on `Bash`, matching the destructive pattern (e.g. `git push --force`/`git push -f` to the primary branch, or `git reset --hard`) and returning a blocking decision. No `|| true`, no stderr suppression yet — that comes after the pipe-test passes.
3. **Pipe-test it** with a synthesized stdin payload matching the real hook-input shape (`{"tool_name":"Bash","tool_input":{"command":"<the exact destructive command this should block>"}}`) piped directly into the constructed command. A blocking `PreToolUse` hook signals via its **output**, not its exit code or any side effect — confirm the blocking case's stdout actually contains a deny decision (`hookSpecificOutput.permissionDecision: "deny"`, or the command exits 2 per the exit-code contract, whichever this hook uses). Also pipe-test one command it should **not** block (e.g. a plain `git push`), and confirm that case's output has no deny decision — an exit-0 "it ran without erroring" is not evidence either direction on its own.
4. **Merge into `<app-dir>/.claude/settings.json`** — read-then-merge, never overwrite existing hooks/permissions/settings already in the file. Create the file (and `.claude/`) only if neither exists.
5. **Validate:** `jq -e '.hooks.PreToolUse[] | select(.matcher == "Bash") | .hooks[] | select(.type == "command") | .command' <app-dir>/.claude/settings.json` — exits 0 and prints the command, or the write is wrong.
6. **Note the watcher caveat** for Task 6's report: a hook added to a `.claude/` directory that didn't exist when the current session started won't fire until `/hooks` is opened once or the session restarts — this skill cannot trigger that itself.

**Verification:** either the hook was pipe-tested against both a blocking and a non-blocking case before being written and `jq -e` confirms the written JSON, or step 1 found a dedup conflict under dispatch and this task was skipped with the conflict noted for Task 6; the watcher caveat was captured, not assumed away.

## Task 5: Write a skill-authoring rule

Every app this bootstraps starts with zero skills — but the first one anyone writes for it needs to follow the current official component specs, not stale training data (skill frontmatter/discovery mechanics, and the path-scoping syntax for the rule file this task itself writes, have both changed across Claude Code versions). Pin that from day one instead of retrofitting it once the app already has an off-spec skill.

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

State what now exists: `CLAUDE.md`'s line count and section summary, the guard hook's exact trigger condition and file location (or that Task 4 was skipped on a dedup conflict, and what conflicted), the `/hooks`-or-restart caveat if it applies, and the skill-authoring rule's source URL/fetch date (or that Task 5 was skipped, and why).

- **Invoked directly by a user in this session:** report inline, in this conversation.
- **Invoked as a dispatched agent:** state it as this turn's own final text output — that *is* the completion signal the caller reads (`herdr agent read` once it detects the turn ended, for `herdr-pane`; this process's own stdout, for `claude-p`). Don't additionally push it through `notifying-main-agent` — that channel is fire-and-forget with no delivery guarantee, not something the caller is depending on for this report.

**Verification:** the report states what was written and what to do (if anything) to make the hook take effect immediately; under dispatch, it's this turn's own final output, not a separate message the caller might never receive.

## Red Flags

- "No non-obvious tooling found, add some general best-practices anyway to look complete" — no, Task 2/3: a short or near-empty `CLAUDE.md` is correct when nothing non-obvious exists.
- "Just CLAUDE.md is fine, skip the hook" — no, this skill's reason to exist beyond writing a file is that prose is roughly-compliance-only; a destructive-action rule needs the hook.
- "Scaffold empty `.claude/skills/`/a full `.claude/rules/` library too, more structure looks more thorough" — no, out of scope for this skill; they earn their place once there's real content. Task 5's one skill-authoring rule is the deliberate exception, not a precedent for adding more.
- "Write the hook and move on, pipe-testing takes an extra step" — no, Task 4 pipe-tests both a blocking and a non-blocking case before writing.
- "Exit code was 0, the pipe-test passed" — no, a blocking `PreToolUse` hook signals through its output, not its exit code; check the actual deny decision is present (blocking case) or absent (non-blocking case).
- "Chain a few guards into one hook while I'm at it" — no, one hook, the single most relevant guard; more can be added later, deliberately, not bundled in here.
- "Overwrite the existing `.claude/settings.json` wholesale" — no, Task 4 step 4: read-then-merge, always.
- "Paraphrase the skill/rule spec from memory instead of fetching it live" — no, Task 5 exists specifically to prevent drift; fetch every time, never reuse a cached understanding from a prior bootstrap.
- "Dispatched and there's no user to confirm Task 1's scope, ask anyway just in case" — no, a dispatch instruction with pre-confirmed scope means don't re-ask; there's no one to answer a `claude -p` dispatch's question.
- "Dispatched, hit a dedup conflict in Task 4 step 1, ask the user anyway" — no, there's no one to answer under `claude -p`; skip the hook, note the conflict for Task 6, and move on.
- "Push the final report through `notifying-main-agent` too, just to be safe" — no, Task 6: under dispatch, this turn's own final output already is the completion signal the caller reads; a second push through a fire-and-forget channel adds nothing the caller is watching for.

## References

None outside this plugin, deliberately — this skill doesn't depend on any other plugin being installed. Task 5's `WebFetch` calls go to a public URL (`code.claude.com`), not to another plugin's skill — that keeps the same zero-plugin-dependency guarantee while still pulling live spec content instead of stale memory.
