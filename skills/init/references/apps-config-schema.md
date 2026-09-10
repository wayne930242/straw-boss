# Apps config schema

The managed-apps list lives at `.straw-boss/apps.json`, relative to the project's repo root — checked into git, shared with the team, edited by `init` (see `SKILL.md`) or by hand. `work-on`, `shipping-task`, and `dispatching-work` all read this file; none of them hardcode an app list.

## 共用讀取 handler

Python 呼叫端使用 `scripts/straw_boss/apps.py` 的 `read_apps_config(repo_root)`，取得 `path`、`payload`、`legacy`。技能在解析 git repo root 後執行：

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/read-apps-config.py" --repo-root "<repo-root>"
```

成功時 exit 0，JSON 包含 `path`（實際來源）、`legacy`（是否使用舊位置）、`config`（完整設定）。兩個位置皆缺少時 exit 3，init／work-on 進入無設定分支；讀取或格式錯誤時 exit 1，依 stderr 修復設定後重試。所有讀取端使用這個 handler，取得設定後才進行各自的 app 欄位檢查。

## 設定位置與相容性

以 git repo root 為基準，優先讀取 `.straw-boss/apps.json`；僅在新路徑不存在時讀取舊位置 `.claude/straw-boss/apps.json`。新路徑存在但無法讀取、JSON 無效或結構無效時，回報該檔案的錯誤。兩檔並存時採用新檔，並在 init 回報舊檔已被取代。

`init` 將使用者確認的設定寫入新路徑；僅有舊檔且選擇保留設定時，完整保留欄位寫入新檔，讀回核對內容，留下舊檔並回報遷移。其他讀取端只讀設定。單一 app 的無設定分支在兩個路徑都不存在時適用。

## 設定格式

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
| `redirectTo` | string \| `null` | no | Another entry's `name`. When set, this entry is a legacy/retired source — new work redirects to the named app instead (`work-on` Task 2). Omit or `null` for a live app. |
| `note` | string \| `null` | no | Free-text caveat surfaced whenever this app is resolved or redirected — e.g. "still looks actively maintained, but new feature work belongs in `api` instead" for a `redirectTo` entry that doesn't read as deprecated. |
| `forbidDirectCommit` | boolean | no | Default `false`. When `true`, `shipping-task` only offers team-mode (worktree→MR) for this app, never a direct commit to its base branch. Solo-mode's commit needs no user authorization, so this field is the only gate standing between an autonomous agent and this app's shared base branch. |
| `agentKind` | string \| `null` | no | Which agent CLI a dispatch into this app defaults to (`"claude"`, `"codex"`, ...). `null`/omitted means `"claude"`. `dispatching-work` can still override it for one dispatch (an explicit `--agent-kind`, or a task judged against root `AGENTS.md` 與 `CLAUDE.md` 的 agent-routing policy if one exists) without changing this stored default. Applies equally to standalone, batch, and Plan tasks. |
| `gitWorkflowSkill` | string \| `null` | no | Name of a project-level skill (in this app's own `.claude/skills/`) that already drives commit/MR/release mechanics. When set, `shipping-task` tells the agent to run that skill's steps instead of its own fallback. |
| `localFiles` | array of objects | no | Gitignored files `git worktree add` won't check out, that a fresh worktree needs. Each entry: `path` (string, relative to `dir`), `sensitive` (boolean, default `false`), `optional` (boolean, default `false`; set `true` only when the app remains operable without it), `note` (string, optional). |
| `crossAppSkills` | array of objects | no | Pointers to an existing project skill that already handles this app depending on another. Each entry: `withApp` (the other app's `name`), `skill` (the skill's name), `note` (string, optional). |

## Reading and writing this file

- **`init`** writes it (its "Resolve the managed apps" task) and keeps it in sync with the root `AGENTS.md` 與 `CLAUDE.md` 的 managed-apps 區段 (its "同步根目錄 AGENTS.md 與 CLAUDE.md" task) — see `init`'s `SKILL.md`, numbered tasks whose order can shift as the skill grows.
- **`work-on`** reads `apps` to build its routing table (Task 1), reads `redirectTo` for the legacy-redirect step (Task 2), and reads `crossAppSkills` for cross-app coordination (Task 3).
- **`shipping-task`** reads `forbidDirectCommit` and `gitWorkflowSkill` per resolved app.
- **`dispatching-work`**'s `references/plan-mechanics.md` reads `localFiles` for the worktree local-file-copy step.
- **`dispatching-work`** reads `agentKind` per resolved app as the default agent CLI for any dispatch (`references/dispatch-mechanics.md`'s "Resolving the agent kind").

A skill whose shared handler returns exit 3 never guesses a *multi*-app list — but a single-app-looking repo still resolves and proceeds without one, via `work-on`'s Task 1 no-config handling (an implicit single app, not a config file). `init` is what makes that app's config durable/customizable; it's not a precondition for a single-app repo to work at all.
