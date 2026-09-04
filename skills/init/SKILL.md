---
name: init
description: One-time (or occasional) setup for straw-boss in a project. Use when the user says "straw-boss init", runs it for the first time in a repo, or another straw-boss skill reports no apps config or no capability record exists yet.
---

## Overview

Three independent one-time decisions, all persisted so no other skill has to ask again: which apps this project manages (project-level, checked into git, shared with the team), which work routes should select each provider profile/model/effort and optional Claude Code native advisor (project-level, written into root `CLAUDE.md`), and whether `herdr-pane` dispatch is available on this machine (per-user, per-machine, lives under the user's home directory). A project can be re-`init`'d to change any one of these without touching the other two.

## Task 1: Check for an existing apps config

Locate the repo root with `git rev-parse --show-toplevel` — never assume the current directory is the root. Read `<repo-root>/.claude/straw-boss/apps.json` (schema: `references/apps-config-schema.md`). If it exists, show the current app list and ask whether the user wants to keep it, add/remove apps, or redo it from scratch — do not silently overwrite it.

- **Keep, no changes:** Task 2 is a no-op — the config already reflects the intended app list, so don't re-run its resolution dialogue. The rest of the skill still runs in full: Task 3's agent-routing question, Tasks 4-8's capability/herdr decisions are independent of the apps list, Task 9 still checks each app for a missing agent system, and Task 10 still re-syncs `CLAUDE.md`, in case that file drifted independently of the config.
- **Add/remove apps, or redo from scratch:** Task 2 runs for real, scoped to what the user asked to change (e.g. only the new apps, not re-confirming ones the user didn't mention).
- **No existing config:** Task 2 runs fresh, as normal.

**Verification:** either no config was found and Task 2 proceeds fresh, or one was found and the user gave an explicit keep/change answer that determined whether Task 2's resolution dialogue actually ran.

## Task 2: Resolve the managed apps

Figure out which directories are the project's apps and how each should be matched. Two ways in, use whichever fits:

1. **Scan for candidates.** Look for a common monorepo layout — `apps/*`, `packages/*`, `services/*`, `cmd/*`, or top-level directories that each contain their own `package.json`/`*.csproj`/`go.mod`/`pyproject.toml`. Present the candidates found and let the user confirm, trim, or add to the list rather than typing every path from scratch.
2. **No obvious layout, or the scan misses something.** Ask directly: app name, and its directory relative to repo root.

For every confirmed app, dispatch bounded reconnaissance rooted in each confirmed app. Candidate scanning in this session is limited to directory names and manifest filenames; the worker reads app content so the app's own agent system and local context load only there. A provisional app name and absolute `repo_root` are enough to launch this one-off investigation before `apps.json` exists.

Each reconnaissance returns proposed fields with evidence references:

- `name` and `match`, grounded in the app's manifest, README, or established terminology;
- `redirectTo` and optional `note`, when app-local evidence identifies a replacement or retirement relationship;
- `forbidDirectCommit`, grounded in the repository's actual workflow or reachable branch policy;
- `agentKind`, only when persistent app-owned provider configuration establishes a project default;
- `gitWorkflowSkill`, when an app-owned skill handles commits, PRs, or releases;
- `localFiles`, limited to existing, untracked, gitignored files, with sensitive material identified for later user approval and `optional: true` only when the app remains operable without that file;
- `crossAppSkills`, when an app-owned skill contains a concrete cross-app path or repository dependency;
- an agent-system inventory for Task 9.

Use a confirmed lower-tier investigation route when it can still produce an explanatory, evidence-backed result. Integrate the reports into one recommendation, show the evidence behind every proposed optional field, and let the user confirm, correct, or add private team policy that the workers could not observe. Empty optional fields are a valid result.

Write the result to `<repo-root>/.claude/straw-boss/apps.json` (same repo-root resolution as Task 1) per `references/apps-config-schema.md`'s exact field names and shapes.

**Verification:** every app in the written config has a `name`, `dir`, and at least one `match` phrase; the coordinator did not read target-app histories, ignore files, skills, or agent instructions; every proposed optional field arrived with evidence references and was confirmed by the user or supplied directly by the user.

## Task 3: Configure work routes

Ask once, project-wide — not per app — whether to configure work routes for dispatched work. A work route maps a description such as "documentation" or "programming" to one complete worker setup. This is independent of Task 2's per-app `agentKind`: that field remains the mechanical provider fallback when no route matches.

If root `CLAUDE.md` already has a `<!-- straw-boss:agent-routing:start/end -->` section, show its current routes and ask whether to keep, edit, remove, or add routes. Preserve a kept route without re-asking each field.

For every new or edited route:

1. Get the work description used for matching.
2. Get the agent kind (`claude` or `codex`) and optional provider profile — Claude's named `--agent` preset or Codex's named `--profile` configuration.
3. Recommend model and reasoning effort. Check that provider's local config, relevant installed routing guidance, and the user's personal root `CLAUDE.md` before proposing values. Use current official guidance only when local evidence gives no clear preference. For bounded investigation, audit, or diagnosis routes, offer a lower-tier model such as Haiku or a lower-tier Codex model when it remains capable of returning an explanatory result with evidence; never trade away the evidence requirement for a binary answer.
4. For a Claude route only, ask whether to use a Claude Code native advisor and, if so, recommend its model. Sonnet with Opus is one documented pairing; availability and accepted pairings still depend on the installed Claude Code account/provider. Codex has no native advisor, so a Codex route records `advisor: none` without offering a coworker or subagent as a substitute.
5. Present the whole route and get explicit confirmation or correction before recording it. Then offer another route.

Write confirmed routes as canonical prose between the routing markers, one line per route: `<work description> → worker: kind=<kind>, profile=<profile|default>, model=<model|default>, effort=<effort|default>; advisor=<model|none>`. Keep this policy in root `CLAUDE.md`, not `apps.json`.

**Verification:** every written route was confirmed as a whole; recommendations used local preferences before current official guidance; only Claude routes can name an advisor; existing routes were presented before replacement; multiple work routes can reuse the same agent kind with different profiles/models; the result lives only between root `CLAUDE.md`'s agent-routing markers.

## Task 4: Check for an existing capability record

Resolve the home directory with `python3 -c "from pathlib import Path; print(Path.home() / '.straw-boss')"` — never write a literal `~/.straw-boss/...` into a command (shell `~` expansion is unreliable across the platforms this tool's users are on). Read `<home>/.straw-boss/capability.json` (schema: `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/dispatch-mechanics.md`). If it already exists, show its current state (`herdr-enabled` or `claude-p-only`) and ask whether the user wants to keep it or change it — do not silently overwrite it, and do not silently skip re-running the rest of this skill just because a record exists.

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

`herdr-pane` tasks can message the main agent directly for coordination questions (see `dispatching-work`'s `references/cross-session-coordination.md`) — but only if incoming cross-session messages actually deliver. Read `~/.claude/settings.json`'s top-level `crossSessionInbound` key.

- **Already `"accept"`:** nothing to do.
- **Unset or anything else:** explain what it does (without it, a message from a session whose permission-mode class doesn't match the main agent's — e.g. a `herdr-pane` agent running in auto/bypass mode messaging a normal interactive session — gets held pending manual review instead of delivering) and ask whether to set it to `"accept"` in the user's global `~/.claude/settings.json`. This is a Claude Code CLI setting, not straw-boss's own — say so, and that `"accept"` only automates delivery, it does not change the standing rule that a peer's message is never treated as authorization for anything.

**Verification:** the user was told what the setting does and asked explicitly before it was changed — this skill never flips it silently.

## Task 9: Offer to bootstrap a missing agent system, per app

Use Task 2's worker-reported agent-system inventory for each app. For an
unchanged configured app that has no current-run report, dispatch the same
bounded inventory rooted in that app. An agent system exists when
`<app-dir>/CLAUDE.md` exists or `<app-dir>/.claude/` contains `skills/`,
`rules/`, or `hooks/`; settings alone are configuration rather than app
guidance.

For an app with an existing agent system, record the evidence and continue. For
an app without one, show that finding and ask whether to bootstrap it through
`create-great-harness`. Ask per app because ownership and generation policy may
differ. `CLAUDE.md` is the only unconditional artifact; optional hook or rule
work requires concrete project evidence or explicit confirmed scope.

For every confirmed bootstrap, dispatch `create-great-harness` through
`dispatching-work` with the app's already-resolved directory and the user's
confirmed scope. Carry that confirmation into the brief. When several apps are
confirmed, they may share a batch label while remaining independent dispatches.
Use `dispatching-work` as the single source for provider routing, instruction
creation, launch confirmation, status observation, and wrap-up.

Before `init` ends, report each bootstrap as terminal and wrapped up, or name
the still-running instruction and how the user can inspect it.

**Verification:** every app has an evidence-backed inventory result; every
bootstrap has an explicit per-app confirmation; app mutations occurred only in
rooted workers; dispatch state and completion follow `dispatching-work`.

## Task 10: Sync the managed-apps section in root CLAUDE.md

**Keep this section minimal.** A monorepo's root `CLAUDE.md` is inherited by every nested session — not just the one running straw-boss's skills, but every session dispatched into an individual app's own directory too (nested `CLAUDE.md` loads walk up to the repo root). Anything written here has its token cost paid by every one of those sessions, every time, unlike `apps.json`, which only the skills that need it read on demand. Names and directories only — no prose, no per-app quirks. `forbidDirectCommit`, `gitWorkflowSkill`, `redirectTo`, `note`, `localFiles`, and `crossAppSkills` all stay in `apps.json` exclusively; never duplicate them here.

**Check for a same-file race before writing.** For an app whose `<app-dir>` resolves to the repo root itself (a single-app repo's own implicit app, or any app whose `dir` is `.`), Task 9 may have dispatched a bootstrap targeting that exact `<app-dir>/CLAUDE.md` — the same file this task is about to edit. If that dispatch hasn't reached terminal status and been wrapped up yet, wait for it (same completion detection as Task 9) before touching root `CLAUDE.md` here; running both concurrently means whichever write lands last silently overwrites the other's content. This never applies to an app whose `dir` is an actual subdirectory — its `CLAUDE.md` is a different file entirely.

Read `<repo-root>/CLAUDE.md` (create it with a one-line project heading if it doesn't exist yet). Render the apps config into markers:

```markdown
<!-- straw-boss:apps:start -->
## Managed apps (straw-boss)

api — apps/api
web — apps/web

Full config (routing, redirects, per-app rules): `.claude/straw-boss/apps.json`.
<!-- straw-boss:apps:end -->
```

If the markers already exist, replace only the content between them — leave the rest of `CLAUDE.md` untouched. If they don't exist, append the block at the end of the file, separated from any existing content by exactly one blank line (so a file that doesn't already end in a newline still renders as valid Markdown, and a file that does doesn't gain extra blank lines). This is the section a future main-agent session reads to know the project's managed scope, so keep it in sync every time Task 2 changes the config, not just on first run.

**Verification:** root `CLAUDE.md` exists and contains an up-to-date managed-apps section between the markers, listing only app names and directories; nothing outside the markers was touched; no per-app rule detail leaked into this section from `apps.json`; if any Task 9 dispatch targeted the repo root itself, it was confirmed terminal before this task wrote root `CLAUDE.md`.

## References

- `references/apps-config-schema.md` — exact `apps.json` field names, types, and how other skills read it.
- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/dispatch-mechanics.md` — `capability.json` schema.
