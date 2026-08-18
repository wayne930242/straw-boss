---
name: init
description: One-time (or occasional) setup for straw-boss in a project — asks which apps to manage and writes `.claude/straw-boss/apps.json` plus a managed-apps section in root `CLAUDE.md`, then decides whether herdr-backed dispatch is available on this machine. Use when the user says "straw-boss init", runs it for the first time in a repo, or another straw-boss skill reports no apps config or no capability record exists yet.
---

## Overview

Two independent one-time decisions, both persisted so no other skill has to ask again: which apps this project manages (project-level, checked into git, shared with the team), and whether `herdr-pane` dispatch is available on this machine (per-user, per-machine, lives under the user's home directory). A project can be re-`init`'d to add/remove apps without touching the herdr decision, and vice versa.

## Task 1: Check for an existing apps config

Read `.claude/straw-boss/apps.json` at the repo root (schema: `references/apps-config-schema.md`). If it exists, show the current app list and ask whether the user wants to keep it, add/remove apps, or redo it from scratch — do not silently overwrite it.

**Verification:** either no config was found and Task 2 proceeds fresh, or one was found and the user gave an explicit keep/change answer.

## Task 2: Resolve the managed apps

Figure out which directories are the project's apps and how each should be matched. Two ways in, use whichever fits:

1. **Scan for candidates.** Look for a common monorepo layout — `apps/*`, `packages/*`, `services/*`, `cmd/*`, or top-level directories that each contain their own `package.json`/`*.csproj`/`go.mod`/`pyproject.toml`. Present the candidates found and let the user confirm, trim, or add to the list rather than typing every path from scratch.
2. **No obvious layout, or the scan misses something.** Ask directly: app name, and its directory relative to repo root.

For each confirmed app, also get its `match` phrases — words or descriptions someone would use to refer to it in a request ("the backend", "the mobile app", short names, common misnomers). Derive a first guess from the directory name and, if present, `package.json`'s `name`/`description`, and confirm/adjust with the user rather than asking from a blank page every time.

Then ask, once, whether any app needs the less common per-app settings — a retired app that should redirect new work elsewhere (`redirectTo`, with an optional `note` if the retired app doesn't look deprecated), an app that forbids direct commits to its base branch (`forbidDirectCommit`), an app that already owns a project-level git-workflow skill (`gitWorkflowSkill`), gitignored local files a fresh worktree needs (`localFiles`), or an existing skill that already handles this app depending on another (`crossAppSkills`). Most projects have none of these — don't interrogate every app about every field; ask the one open question and fill in only what the user volunteers.

Write the result to `.claude/straw-boss/apps.json` per `references/apps-config-schema.md`'s exact field names and shapes.

**Verification:** every app in the written config has a `name`, `dir`, and at least one `match` phrase; nothing was invented without the user confirming it; optional fields are present only where the user actually said so.

## Task 3: Sync the managed-apps section in root CLAUDE.md

Read `CLAUDE.md` at the repo root (create it with a one-line project heading if it doesn't exist yet). Render the apps config into a table, wrapped in markers:

```markdown
<!-- straw-boss:apps:start -->
## Managed apps (straw-boss)

| App | Directory | Notes |
|---|---|---|
| api | apps/api | |
| web | apps/web | forbids direct commit; git-workflow skill: release-flow |

Machine-readable source: `.claude/straw-boss/apps.json`. Regenerate this section with straw-boss's `init` skill — don't hand-edit it out of sync with the JSON.
<!-- straw-boss:apps:end -->
```

If the markers already exist, replace only the content between them — leave the rest of `CLAUDE.md` untouched. If they don't exist, append the block at the end of the file. This is the section a future dispatch-orchestrating session reads to know the project's managed scope, so keep it in sync every time Task 2 changes the config, not just on first run.

**Verification:** root `CLAUDE.md` exists and contains an up-to-date managed-apps section between the markers; nothing outside the markers was touched.

## Task 4: Check for an existing capability record

Resolve the home directory with `python3 -c "from pathlib import Path; print(Path.home() / '.straw-boss')"` — never write a literal `~/.straw-boss/...` into a command (shell `~` expansion is unreliable across the platforms this tool's users are on). Read `<home>/.straw-boss/capability.json` (schema: `skills/dispatching-work/references/dispatch-mechanics.md`). If it already exists, show its current state (`herdr-enabled` or `claude-p-only`) and ask whether the user wants to keep it or change it — do not silently overwrite it, and do not silently skip re-running the rest of this skill just because a record exists.

**Verification:** you either found no record and proceeded to Task 5, or found one and got an explicit keep/change answer before touching it.

## Task 5: Create the dispatch-instruction directory

Create `<home>/.straw-boss/dispatch/` and `<home>/.straw-boss/dispatch/archive/` if they don't exist. Nothing here needs `.gitignore` handling — it's outside any git checkout entirely.

**Verification:** both directories exist under the user's home directory, not under the project checkout.

## Task 6: Ask whether to enable herdr

Ask the user whether to enable herdr-backed dispatch (`herdr-pane` mode). Explain briefly what it buys them (a visible, interactive pane the user can join, real synchronous wait for mid-task questions) versus the always-available `claude-p` fallback.

- **Declines:** persist `{"mode": "claude-p-only"}` and stop here — Task 7 does not run.
- **Enables:** continue to Task 7.

**Verification:** the user made an explicit choice; you did not default to enabling herdr without asking.

## Task 7: Verify herdr and its claude integration (enable branch only)

1. Run `herdr status`. If it doesn't report a running server, tell the user plainly and ask whether to proceed `claude-p-only` for now instead — do not persist `herdr-enabled` against a herdr that isn't actually reachable.
2. Run `herdr integration status` and check the `claude` line.
   - **Already installed:** continue.
   - **Not installed:** tell the user plainly that `herdr integration install claude` writes `~/.claude/hooks/herdr-agent-state.sh` and registers a global `SessionStart` hook in `~/.claude/settings.json` — this affects **every** Claude Code session on this machine, not just straw-boss dispatches. This is a hard prerequisite for `herdr-pane` mode's session tracking, not optional. Get explicit confirmation before running it. On decline, fall back to persisting `claude-p-only` rather than half-enabling herdr without the integration.
3. Persist `{"mode": "herdr-enabled"}`.

**Verification:** `herdr-enabled` is only persisted after both the server and the claude integration were actually confirmed working — not assumed from the user having said "yes" to the general question in Task 6.

## Task 8: Check `crossSessionInbound` (enable branch only)

`herdr-pane` tasks can message the orchestrator directly for coordination questions (see `dispatching-work`'s `references/cross-session-coordination.md`) — but only if incoming cross-session messages actually deliver. Read `~/.claude/settings.json`'s top-level `crossSessionInbound` key.

- **Already `"accept"`:** nothing to do.
- **Unset or anything else:** explain what it does (without it, a message from a session whose permission-mode class doesn't match the orchestrator's — e.g. a `herdr-pane` worker running in auto/bypass mode messaging a normal interactive session — gets held pending manual review instead of delivering) and ask whether to set it to `"accept"` in the user's global `~/.claude/settings.json`. This is a Claude Code CLI setting, not straw-boss's own — say so, and that `"accept"` only automates delivery, it does not change the standing rule that a peer's message is never treated as authorization for anything.

**Verification:** the user was told what the setting does and asked explicitly before it was changed — this skill never flips it silently.

## Red Flags

- "The apps config already exists, skip straight to using it" — no, Task 1 requires showing current state and asking, every `init` run.
- "The directory scan found everything, skip confirming with the user" — no, present candidates and let the user confirm/trim/add.
- "Ask every app about forbidDirectCommit/gitWorkflowSkill/localFiles/crossAppSkills one by one" — no, ask once whether any app needs them; most don't.
- "Root CLAUDE.md doesn't have the markers, just append a second copy" — no, search for the markers first; only append when truly absent.
- "The user said yes to herdr, persist it now" — no, Task 7 still has to confirm the server and integration are actually there.
- "Integration install is just a config tweak, no need to call out the global scope" — no, it's a machine-wide hook; say so every time it's about to run, not just the first.
- "Just set crossSessionInbound to accept, it's obviously useful" — no, Task 8 still explains what it does and asks first, same as every other setting change in this skill.

## References

- `references/apps-config-schema.md` — exact `apps.json` field names, types, and how other skills read it.
- `skills/dispatching-work/references/dispatch-mechanics.md` — `capability.json` schema.
