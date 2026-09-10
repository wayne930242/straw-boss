---
name: init
description: Use on straw-boss's first run in a repo, or when another straw-boss skill reports no apps config.
---

## Overview

Configure the project's managed apps and work routes, and check the Herdr dependency a dispatch needs. Configuration and instruction sync can complete on their own; starting a dispatch needs a running Herdr service and a current pane.

## Task 1: Check for an existing apps config

Locate the repo root with `git rev-parse --show-toplevel` — never assume the current directory is the root. Run the shared read handler in `references/apps-config-schema.md`, and read its exit code to tell a present config from a missing one and from a config error. The returned `config` is the basis for every edit below; `path` and `legacy` are the migration evidence. If it exists, show the current app list and ask whether the user wants to keep it, add/remove apps, or redo it from scratch — do not silently overwrite it.

- **Keep, no changes:** keep the app list and skip Task 2's confirmation dialogue; where the source was the old path, write it to the new path per the schema's migration rule. The rest of the skill still runs in full: Task 3's agent-routing question, the Herdr checks in Task 4 are independent of the apps list, Task 5 still checks each app for a missing agent system, and Task 6 still re-syncs `AGENTS.md` and `CLAUDE.md`, in case those files drifted independently of the config.
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
- an agent-system inventory for Task 5.

Use a confirmed lower-tier investigation route when it can still produce an explanatory, evidence-backed result. Integrate the reports into one recommendation, show the evidence behind every proposed optional field, and let the user confirm, correct, or add private team policy that the workers could not observe. Empty optional fields are a valid result.

Write the result to `<repo-root>/.straw-boss/apps.json` (same repo-root resolution as Task 1) per `references/apps-config-schema.md`'s exact field names and shapes.

**Verification:** every app in the written config has a `name`, `dir`, and at least one `match` phrase; the coordinator did not read target-app histories, ignore files, skills, or agent instructions; every proposed optional field arrived with evidence references and was confirmed by the user or supplied directly by the user.

## Task 3: Configure work routes

Ask once, project-wide — not per app — whether to configure work routes for dispatched work. A work route maps a description such as "documentation" or "programming" to one complete worker setup. This is independent of Task 2's per-app `agentKind`: that field remains the mechanical provider fallback when no route matches.

If either root `AGENTS.md` or `CLAUDE.md` already has a `<!-- straw-boss:agent-routing:start/end -->` section, show its current routes and ask whether to keep, edit, remove, or add routes. Preserve a kept route without re-asking each field.

Read the routing section of both files first, creating a missing file with a one-line project heading. Where only one carries a section, take it; where both agree, keep it; where they differ, present the difference for the user to settle, then sync the confirmed content. Writes stay inside the routing markers, and each file keeps everything outside them.

For every new or edited route:

1. Get the work description used for matching.
2. Get the agent kind (`claude` or `codex`) and optional provider profile — Claude's named `--agent` preset or Codex's named `--profile` configuration.
3. Recommend model and reasoning effort. Check that provider's local config, relevant installed routing guidance, and the user's personal root `AGENTS.md` and `CLAUDE.md` before proposing values. Use current official guidance only when local evidence gives no clear preference. For bounded investigation, audit, or diagnosis routes, offer a lower-tier model such as Haiku or a lower-tier Codex model when it remains capable of returning an explanatory result with evidence; never trade away the evidence requirement for a binary answer.
4. For a Claude route only, ask whether to use a Claude Code native advisor and, if so, recommend its model. Sonnet with Opus is one documented pairing; availability and accepted pairings still depend on the installed Claude Code account/provider. Codex has no native advisor, so a Codex route records `advisor: none` without offering a coworker or subagent as a substitute.
5. Present the whole route and get explicit confirmation or correction before recording it. Then offer another route.

Write confirmed routes as canonical prose between the routing markers, one line per route: `<work description> → worker: kind=<kind>, profile=<profile|default>, model=<model|default>, effort=<effort|default>; advisor=<model|none>`. Keep this policy in root `AGENTS.md` and `CLAUDE.md` rather than `apps.json`.

**Verification:**

- every written route was confirmed as a whole;
- recommendations used local preferences before current official guidance;
- only Claude routes can name an advisor;
- existing routes were presented before replacement;
- multiple work routes can reuse the same agent kind with different profiles/models;
- the result is written only inside the agent-routing markers of root `AGENTS.md` and `CLAUDE.md`.

## Task 4: Set up dispatch state and verify readiness

Create `.straw-boss/dispatch/` and `.straw-boss/dispatch/archive/` under the user's home (resolved with Python's `Path.home()`), then check each dispatch dependency against what it actually reports:

- **CLI and service** — `command -v herdr` and `herdr status`.
- **Current session** — the live agent record for `$HERDR_PANE_ID`, and its provider identity.
- **Provider integration** — `herdr integration status` for this worker provider. Where the Claude integration is missing, explain that `herdr integration install claude` writes a global Claude hook and settings, then install it with the user's authorization and check the result. Codex is validated through the provider session and terminal identity in the live record.

An unmet condition doesn't stop this skill: report it, and local configuration and Task 6's instruction sync still complete. Task 5's per-app dispatch waits for readiness. The mode is always `herdr-pane`, and readiness is re-checked at every dispatch entry point.

**Verification:** every dependency's actual state was observed; configuration completion and dispatch readiness are reported as separate claims.

## Task 5: Offer to bootstrap a missing agent system, per app

Use Task 2's worker-reported agent-system inventory for each app. For an
unchanged configured app that has no current-run report, dispatch the same
bounded inventory rooted in that app.

Either of these means an agent system already exists:
`<app-dir>/AGENTS.md` or `<app-dir>/CLAUDE.md` exists, or the app's `.agents/skills/`, `.claude/skills/`, `.claude/rules/`, or `.claude/hooks/` carries project instructions. Settings themselves count as configuration.

Record the evidence for an app that already has one. Where `AGENTS.md` or `CLAUDE.md` is missing, offer to fill the gap through `create-great-harness` while keeping the existing instructions; with both present, move on. For an app with no agent system at all, offer to create both instruction files. Scope is confirmed per app, and the confirmed scope is what goes to bootstrap.

`AGENTS.md` and `CLAUDE.md` are required bootstrap outputs; an optional hook or rule is created only from concrete project evidence or confirmed scope.

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

## Task 6: Sync the root AGENTS.md and CLAUDE.md

Wait for Task 5's bootstrap of the repo-root app to finish and clean up before writing the instruction files in that same root.

Read `<repo-root>/AGENTS.md` and `<repo-root>/CLAUDE.md`, creating a missing file with a one-line project heading first. Sync the same apps summary into both. List only app names, directories, and the config location; each app's detailed policy stays in `apps.json`.

```markdown
<!-- straw-boss:apps:start -->
## Managed apps (straw-boss)

api — apps/api
web — apps/web

Full config (routing, redirects, per-app rules): `.straw-boss/apps.json`.
<!-- straw-boss:apps:end -->
```

Where the markers already exist, replace only the section content; where they are missing, append the section after one blank line. Each file keeps everything outside its section. A later `init` run re-syncs both summaries and checks that Task 3's confirmed routing section matches across the two files.

**Verification:** both root instruction files exist, the apps section matches the configuration, the routing section matches Task 3's decision, content outside the sections is preserved, and the write happened only after the root bootstrap completed.

## References

- `references/apps-config-schema.md` — exact `apps.json` field names, types, and how other skills read it.
- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/dispatch-mechanics.md` — the Herdr dispatch interface.
