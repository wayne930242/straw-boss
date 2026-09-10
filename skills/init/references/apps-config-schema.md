# Apps config schema

The managed-apps list lives at `.straw-boss/apps.json`, relative to the project's repo root — checked into git, shared with the team, edited by `init` (see `SKILL.md`) or by hand. `work-on`, `shipping-task`, and `dispatching-work` all read this file; none of them hardcode an app list.

## Shared read handler

Python callers use `read_apps_config(repo_root)` from `scripts/straw_boss/apps.py`, which returns `path`, `payload`, and `legacy`. A skill runs this once it has resolved the git repo root:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/read-apps-config.py" --repo-root "<repo-root>"
```

Success is exit 0, with JSON carrying `path` (the source actually read), `legacy` (whether the old location was used), and `config` (the whole configuration); exit 3 means neither location exists, which sends `init` and `work-on` down their no-config branch; exit 1 means a read or format error — fix the config from stderr and retry. Every reader goes through this handler, and checks its own app fields only after it has the configuration.

## Location and compatibility

Relative to the git repo root, `.straw-boss/apps.json` is read first; the old location `.claude/straw-boss/apps.json` is read only when the new path does not exist. Where the new path exists but is unreadable, invalid JSON, or structurally invalid, report that file's error. With both present, the new file wins and `init` reports that the old one has been superseded.

`init` writes the user-confirmed configuration to the new path. With only the old file present and the user keeping that configuration, every field is preserved into the new file, read back and checked, and the old file is left in place with the migration reported. Every other reader only reads. The single-app no-config branch applies when neither path exists.

## Configuration format

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
        {"path": ".env", "sensitive": true, "optional": false, "note": "carries live DB credentials"}
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
| `redirectTo` | string \| `null` | no | Another entry's `name`. When set, this entry is a legacy/retired source — new work redirects to the named app instead ([work-on](../../work-on/SKILL.md#resolve-the-app)). Omit or `null` for a live app. |
| `note` | string \| `null` | no | Free-text caveat surfaced whenever this app is resolved or redirected — e.g. "still looks actively maintained, but new feature work belongs in `api` instead" for a `redirectTo` entry that doesn't read as deprecated. |
| `forbidDirectCommit` | boolean | no | Default `false`. When `true`, `shipping-task` only offers team-mode (worktree→MR) for this app, never a direct commit to its base branch. The selected mode follows the established lifecycle authorization. |
| `agentKind` | string \| `null` | no | Which agent CLI a dispatch into this app defaults to (`"claude"`, `"codex"`, ...). `null`/omitted means `"claude"`. `dispatching-work` can still override it for one dispatch (an explicit `--agent-kind`, or a task judged against the agent-routing policy in root `AGENTS.md` and `CLAUDE.md` if one exists) without changing this stored default. Applies equally to standalone, batch, and Plan tasks. |
| `gitWorkflowSkill` | string \| `null` | no | Name of a project-level skill (in this app's own `.claude/skills/`) that already drives commit/MR/release mechanics. When set, `shipping-task` tells the agent to run that skill's steps instead of its own fallback. |
| `localFiles` | array of objects | no | Gitignored files `git worktree add` won't check out, that a fresh worktree needs. Each entry: `path` (string, relative to `dir`), `sensitive` (boolean, default `false`), `optional` (boolean, default `false`; set `true` only when the app remains operable without it), `note` (string, optional). |
| `crossAppSkills` | array of objects | no | Pointers to an existing project skill that already handles this app depending on another. Each entry: `withApp` (the other app's `name`), `skill` (the skill's name), `note` (string, optional). |

## Owners

- [init](../SKILL.md) writes configuration and synchronizes root instruction summaries.
- [work-on](../../work-on/SKILL.md) reads app matching, redirects, and cross-app skill pointers.
- [shipping-task](../../shipping-task/SKILL.md) reads lifecycle options; [worktree preparation](../../dispatching-work/references/plan-mechanics.md#worktree-ownership) reads `localFiles`.
- [dispatching-work](../../dispatching-work/SKILL.md) resolves provider setup using the app default and work routes.

A missing configuration uses `work-on`'s implicit single-app branch or an unresolved multi-app question.
