# Apps config schema

The managed-apps list lives at `.claude/straw-boss/apps.json`, relative to the project's repo root — checked into git, shared with the team, edited by `init` (see `SKILL.md`) or by hand. `work-on`, `shipping-task`, and `dispatching-work` all read this file; none of them hardcode an app list.

```json
{
  "apps": [
    {
      "name": "api",
      "dir": "apps/api",
      "match": ["backend api", "rest api", "server"],
      "redirectTo": null,
      "note": null,
      "forbidDirectCommit": false,
      "agentKind": null,
      "gitWorkflowSkill": null,
      "localFiles": [
        {"path": ".env", "sensitive": true, "note": "carries live DB credentials"}
      ],
      "crossAppSkills": [
        {"withApp": "web", "skill": "handle-be-block", "note": "web already has a skill for backend-contract-missing situations"}
      ]
    },
    {
      "name": "api-v1",
      "dir": "apps/api-legacy",
      "match": ["legacy api", "old backend"],
      "redirectTo": "api"
    }
  ]
}
```

## Field reference

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | Unique identifier, matches how the team refers to the app. Kebab-case recommended. |
| `dir` | string | yes | Path to the app's own checkout, relative to repo root. |
| `match` | array of strings | yes | Phrases a request might use to name this app. `work-on`'s routing table is built from these. |
| `redirectTo` | string \| `null` | no | Another entry's `name`. When set, this entry is a legacy/retired source — new work redirects to the named app instead (`work-on` Task 2). Omit or `null` for a live app. |
| `note` | string \| `null` | no | Free-text caveat surfaced whenever this app is resolved or redirected — e.g. "still looks actively maintained, but new feature work belongs in `api` instead" for a `redirectTo` entry that doesn't read as deprecated. |
| `forbidDirectCommit` | boolean | no | Default `false`. When `true`, `shipping-task` only offers the full worktree→MR flow for this app, never a direct commit to its base branch. Light flow's commit needs no user authorization, so this field is the only gate standing between an autonomous agent and this app's shared base branch. |
| `agentKind` | string \| `null` | no | Which agent CLI a dispatch into this app defaults to (`"claude"`, `"codex"`, ...). `null`/omitted means `"claude"`. `dispatching-work` can still override it for one dispatch (an explicit `--agent-kind`, or a task judged against root `CLAUDE.md`'s agent-routing policy if one exists) without changing this stored default. Never used for a plan or batch task — those always dispatch as `"claude"` regardless of this field. |
| `gitWorkflowSkill` | string \| `null` | no | Name of a project-level skill (in this app's own `.claude/skills/`) that already drives commit/MR/release mechanics. When set, `shipping-task` tells the agent to run that skill's steps instead of its own fallback. |
| `localFiles` | array of objects | no | Gitignored files `git worktree add` won't check out, that a fresh worktree needs. Each entry: `path` (string, relative to `dir`), `sensitive` (boolean, default `false`), `note` (string, optional). |
| `crossAppSkills` | array of objects | no | Pointers to an existing project skill that already handles this app depending on another. Each entry: `withApp` (the other app's `name`), `skill` (the skill's name), `note` (string, optional). |

## Reading and writing this file

- **`init`** writes it (its "Resolve the managed apps" task) and keeps it in sync with the root `CLAUDE.md` managed-apps section (its "Sync the managed-apps section in root CLAUDE.md" task) — see `init`'s `SKILL.md`, numbered tasks whose order can shift as the skill grows.
- **`work-on`** reads `apps` to build its routing table (Task 1), reads `redirectTo` for the legacy-redirect step (Task 2), and reads `crossAppSkills` for cross-app coordination (Task 3).
- **`shipping-task`** reads `forbidDirectCommit` and `gitWorkflowSkill` per resolved app.
- **`dispatching-work`**'s `references/plan-mechanics.md` reads `localFiles` for the worktree local-file-copy step.
- **`dispatching-work`** reads `agentKind` per resolved app as the default agent CLI for a standalone dispatch (`references/dispatch-mechanics.md`'s "Resolving the agent kind").

A skill that can't find `.claude/straw-boss/apps.json` at all never guesses a *multi*-app list — but a single-app-looking repo still resolves and proceeds without one, via `work-on`'s Task 1 no-config handling (an implicit single app, not a config file). `init` is what makes that app's config durable/customizable; it's not a precondition for a single-app repo to work at all.
