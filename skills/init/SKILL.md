---
name: init
description: One-time (or occasional) setup for straw-boss in a project. Use when the user says "straw-boss init", runs it for the first time in a repo, or another straw-boss skill reports no apps config or no capability record exists yet.
---

## Overview

Three independent one-time decisions, all persisted so no other skill has to ask again: which apps this project manages (project-level, checked into git, shared with the team), whether any dispatched work should route to an agent kind other than `claude` and what its model/effort should be (project-level, written into root `CLAUDE.md`), and whether `herdr-pane` dispatch is available on this machine (per-user, per-machine, lives under the user's home directory). A project can be re-`init`'d to change any one of these without touching the other two.

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

For each confirmed app, also get its `match` phrases — words or descriptions someone would use to refer to it in a request ("the backend", "the mobile app", short names, common misnomers). Derive a first guess from the directory name and, if present, `package.json`'s `name`/`description`, and confirm/adjust with the user rather than asking from a blank page every time.

Then ask, once, whether any app needs the less common per-app settings — a retired app that should redirect new work elsewhere (`redirectTo`, with an optional `note` if the retired app doesn't look deprecated), an app that forbids direct commits to its base branch (`forbidDirectCommit`), an app whose dispatches should default to a non-`claude` agent CLI (`agentKind` — most apps leave this unset; see Task 3 for the separate, project-wide work-type routing question), an app that already owns a project-level git-workflow skill (`gitWorkflowSkill`), gitignored local files a fresh worktree needs (`localFiles`), or an existing skill that already handles this app depending on another (`crossAppSkills`). Most projects have none of these — don't interrogate every app about every field; ask the one open question and fill in only what the user volunteers.

Write the result to `<repo-root>/.claude/straw-boss/apps.json` (same repo-root resolution as Task 1) per `references/apps-config-schema.md`'s exact field names and shapes.

**Verification:** every app in the written config has a `name`, `dir`, and at least one `match` phrase; nothing was invented without the user confirming it; optional fields are present only where the user actually said so.

## Task 3: Offer additional agent kinds and their routing policy

Ask once, project-wide — not per app — whether to enable one or more agent kinds beyond `claude` for dispatched work (e.g. `codex`). This is independent of Task 2's per-app `agentKind` field: that field is a mechanical fallback for an app whose team always uses a given CLI; this task is about routing specific *kinds of work* to a non-default agent kind, recorded as policy the main agent reads at dispatch time.

- **Declines:** nothing to record, move on to Task 4.
- **Enables:** for each agent kind the user wants — a second, and a third if they want it, not capped at one:
  1. Ask what kind of work should route to it (e.g. "deep debugging and adversarial review", "mechanical extraction and formatting").
  2. Recommend a model and reasoning-effort for that work. Ground the recommendation in whatever local preference already exists before proposing anything — check that agent CLI's own config (e.g. `~/.codex/config.toml`'s `model`/`model_reasoning_effort`), any relevant installed plugin skill's own routing rule (e.g. `codex:codex-cli-runtime`), and the user's personal root `CLAUDE.md` if it already documents a preference for that agent kind. Only fall back to a fresh web search for current provider-recommended defaults when none of those give a clear answer for the work type described. Present the recommendation and get an explicit confirmation or override — never record an unconfirmed guess.
  3. Ask whether to configure another agent kind the same way, looping until the user is done.

Write every confirmed (agent kind, kind of work, model, effort) as a new prose section in root `CLAUDE.md` — not into `apps.json` — since it's read as project-wide policy by every session working in this repo, the same way a personal `CLAUDE.md` might keep its own model-routing table for the same purpose. Use the same marker convention as Task 10's managed-apps section (a dedicated `<!-- straw-boss:agent-routing:start/end -->` pair) so a later `init` run can find and update it without duplicating or clobbering the rest of the file.

**Verification:** the question was asked once for the whole project, not per app; every enabled agent kind's recommendation was grounded in an existing local preference before falling back to a web search, and was confirmed or overridden by the user before being recorded; more than one additional agent kind was allowed, not capped at a single toggle; the result was written into root `CLAUDE.md` between its own markers, never into `apps.json`.

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

For each app resolved in Task 2 (newly added or already-configured — this check is about the app's own directory, not about whether `apps.json` itself changed this run), check whether it already has any agent system at all: does `<app-dir>/CLAUDE.md` exist, **or** does `<app-dir>/.claude/` contain any of `skills/`, `rules/`, `hooks/`? A `.claude/` holding only `settings.json` is not an agent system — permissions/plugin config alone isn't guidance or enforcement, so it doesn't count as exempt.

- **Either condition met:** nothing to do for this app — some agent system is already there, even a minimal one; this task doesn't second-guess its adequacy.
- **Neither:** tell the user this app has no agent system yet, and ask whether to bootstrap a lightweight one now — a `CLAUDE.md`, one guard hook, and one skill-authoring rule, via `create-great-harness` — or skip it. Ask per app, not once for the whole batch; a vendored or generated app, for instance, may deliberately warrant none.
  - **Yes:** this answer *is* the confirmation `create-great-harness`'s own Task 1 would otherwise ask for — carry that into the dispatch instruction below rather than asking the user twice.
  - **Skip:** move on. This check is live, not a remembered decision — a future `init` run checks again, but stops asking the moment the exemption condition is actually met, however it got there.

**Dispatch, don't invoke inline.** `create-great-harness` writes into the app's own checkout (`<app-dir>/CLAUDE.md`, `<app-dir>/.claude/settings.json`, `<app-dir>/.claude/rules/`) — the same reason every other mutation into an app directory goes through `dispatching-work` rather than running from this session's own cwd. Two things differ from how a specialist skill like `shipping-task` normally reaches `dispatching-work`, and both are deliberate, not gaps:

- **No `work-on` call.** The app is already resolved — it came straight from Task 2's `apps.json`, with nothing ambiguous to classify. `work-on` exists to resolve a request *to* an app; there's no request to resolve here.
- **No execution-tier judgment.** Unlike a `boss-say`-routed item, there's no "does this need the app's own harness" question to weigh — the app by definition has none yet, and the whole point of this task is to create it in the app's own directory. Every "yes" dispatches, full stop.

For each app the user said yes to: assemble the task description for `dispatching-work` — `create-great-harness`'s own scope for `<app-dir>`, stated as already confirmed so its Task 1 doesn't re-ask, plus the standard `notifying-main-agent` coordination pointer (main-agent reachability info for this dispatch's mode) for anything genuinely informational it needs to ask mid-task — not as how completion gets detected, see below. If more than one app needs bootstrapping this run, share one batch label (`dispatching-work`'s Task 2) across them. Dispatch each through `dispatching-work`'s Tasks 1-5 — never its "Branch: Dispatch a plan," since there's no dependency graph here, just independent single-app dispatches. Track each with `TaskCreate` (one per app, mirroring `shipping-task`'s own Task Initialization) — this spans until each dispatch reports back, not just the ask.

**Detect completion mechanically, not by waiting on a courtesy message.** `notifying-main-agent` is fire-and-forget with no delivery guarantee (its own Task 1/Task 3, and `dispatching-work`'s own checkpoint table: "not a status transition at all") — there's also no plan-style status file for a non-plan dispatch to poll (`dispatch-mechanics.md`). Use the mechanism each mode actually gives you instead:

- **`claude-p`:** run each dispatch in the background (`run_in_background`) so independent apps' bootstraps run concurrently rather than serializing this turn; the harness's own background-task notification, once it fires, carries the process's final output — that *is* the report.
- **`herdr-pane`:** complete `dispatching-work`'s full Tasks 1-5 for that app first — through step 6.5's delivery confirmation, the session-id cross-check, and step 8's flip to `in-progress` — before starting the wait. Don't launch it right after step 6's submission: step 6.5 exists specifically because a first-run interruption can swallow the submitted text while `herdr agent prompt --wait` still reports success, and a wait started before that's ruled out can catch the agent still idle on an unanswered prompt and misread it as a finished, empty bootstrap. Once Task 4 is genuinely done for that app, run `herdr agent wait "<name>" --until idle --until blocked --timeout 120000` (repeated-`--until` form — see `dispatch-mechanics.md`'s note on this) per app as a background `Bash` call, so multiple apps' waits still run concurrently. A `blocked` return is not completion — it means the agent stalled on a prompt mid-task; surface that to the user rather than wrapping it up as done. On `idle`, `herdr agent read "<name>" --lines 40` to pull the actual report (`create-great-harness`'s own Task 6 output). On timeout, treat it the same as "hasn't reported back yet" below — still running, not failed.

Confirm what was created against each report, then call `dispatching-work`'s wrap-up branch to close the instruction and any pane/tab it used. Dispatch every app's bootstrap independently as soon as its own yes/skip answer lands — the concurrency lives in running these background waits together (once each dispatch's own Tasks 1-5 are done), not in serializing the dispatches themselves.

Before this run of `init` ends, every bootstrap dispatch it started this run should be terminal and wrapped up. If one hasn't reported back yet, tell the user it's still running and how to check on it (`dispatching-work`'s List branch, or `peeking-work`) rather than holding this turn open indefinitely.

**Verification:** every app from Task 2 was checked against the exemption condition above, not just "does `.claude/` exist"; an app that already met it was never asked; an app that didn't got an explicit yes/skip answer before this task moved on; every "yes" was dispatched (never run inline in this session), with the confirmation carried into the instruction rather than re-asked; for `herdr-pane`, the completion wait was started only after that app's own dispatch reached step 8 (delivery confirmed, `in-progress`), never right after submission; a `blocked` wait result was surfaced, never wrapped up as done; completion was detected via the process/background notification (`claude-p`) or `agent wait` + `agent read` (`herdr-pane`), never assumed from a `notifying-main-agent` message that may never arrive; every bootstrap dispatch this run started is either wrapped up or explicitly flagged as still running before this run of `init` ends.

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

## Red Flags

- "The apps config already exists, skip straight to using it" — no, Task 1 requires showing current state and asking, every `init` run.
- "The directory scan found everything, skip confirming with the user" — no, present candidates and let the user confirm/trim/add.
- "Ask every app about forbidDirectCommit/gitWorkflowSkill/localFiles/crossAppSkills one by one" — no, ask once whether any app needs them; most don't.
- "Root CLAUDE.md doesn't have the markers, just append a second copy" — no, search for the markers first; only append when truly absent.
- "Add the Notes column back, it's more useful at a glance" — no, per Task 10: every nested session inherits root `CLAUDE.md`, so per-app detail belongs in `apps.json` only, never duplicated into the root file.
- "The user said yes to herdr, persist it now" — no, Task 7 still has to confirm the server and integration are actually there.
- "Integration install is just a config tweak, no need to call out the global scope" — no, it's a machine-wide hook; say so every time it's about to run, not just the first.
- "Just set crossSessionInbound to accept, it's obviously useful" — no, Task 8 still explains what it does and asks first, same as every other setting change in this skill.
- "An app has neither CLAUDE.md nor .claude/, but it's probably fine, skip asking" — no, Task 9 asks explicitly per app; only an app that meets the exemption condition is skipped.
- "The app has a `.claude/settings.json` with a couple of permission rules, that counts as having an agent system" — no, Task 9: settings alone isn't guidance or enforcement; the exemption needs `CLAUDE.md` or actual `skills/`/`rules/`/`hooks/` content.
- "Ask once for the whole app list whether to bootstrap agent systems" — no, Task 9: per app, since a vendored/generated app may deliberately warrant none.
- "This app's bootstrap is quick, just do it inline in this session instead of dispatching" — no, Task 9: `create-great-harness` writes into the app's own checkout, same reason every other mutation into an app directory gets dispatched rather than run from this session's own cwd.
- "The user already said yes per-app, but let `create-great-harness` ask again too, as a safety net" — no, Task 9's dispatch instruction carries the confirmation; a second ask has no one to answer it under `claude -p` and is redundant under `herdr-pane`.
- "Several apps need bootstrapping, dispatch them one at a time and wait for each before starting the next" — no, Task 9: they're independent; dispatch every yes as soon as it lands.
- "This run of `init` is otherwise done, leave a bootstrap dispatch running and end the turn" — no, Task 9: confirm each dispatch is terminal and wrapped up, or explicitly tell the user it's still running, before the run ends.
- "Wait for the dispatched agent's `notifying-main-agent` message to know it's done" — no, that channel is fire-and-forget with no delivery guarantee; Task 9 detects completion via the process/background notification (`claude-p`) or `agent wait`/`agent read` (`herdr-pane`), never by waiting on a courtesy message that might never arrive.
- "Submitted the task, start the completion wait right away" — no, Task 9: finish `dispatching-work`'s Tasks 1-5 for that app first (through step 6.5's delivery confirmation and step 8's `in-progress` flip); a wait started right after submission can catch a swallowed first-run prompt and misread the still-idle agent as a finished, empty bootstrap.
- "`agent wait` came back, that means the bootstrap finished" — no, Task 9: `blocked` means the agent stalled on a prompt, not that it's done; only `idle` (confirmed via `agent read`'s actual content) means the turn ended.
- "The bootstrapped app's dir is the repo root, sync root CLAUDE.md in Task 10 right away like any other run" — no, per Task 10: check whether Task 9 dispatched into that exact `<app-dir>` and wait for it to finish first — both tasks would otherwise write the same file concurrently.

## References

- `references/apps-config-schema.md` — exact `apps.json` field names, types, and how other skills read it.
- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/dispatch-mechanics.md` — `capability.json` schema.
