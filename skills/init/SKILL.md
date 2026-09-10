---
name: init
description: One-time (or occasional) setup for straw-boss in a project. Use when the user says "straw-boss init", runs it for the first time in a repo, or another straw-boss skill reports no apps config .
---

## Overview

設定專案 managed apps 與 work routes，並檢查委派所需的 Herdr。設定與指引同步可獨立完成；啟動委派時需要可用的 Herdr 服務及目前 pane。

## Task 1: Check for an existing apps config

Locate the repo root with `git rev-parse --show-toplevel` — never assume the current directory is the root. 執行 `references/apps-config-schema.md` 的共用讀取 handler，依 exit code 區分有設定、缺設定與設定錯誤。以回傳的 `config` 作為後續修改基礎，`path` 與 `legacy` 作為遷移證據。 If it exists, show the current app list and ask whether the user wants to keep it, add/remove apps, or redo it from scratch — do not silently overwrite it.

- **Keep, no changes:** 保留 app 清單，略過 Task 2 的確認對話；若來源為舊路徑，依 schema 的遷移規則寫入新路徑。 The rest of the skill still runs in full: Task 3's agent-routing question, Tasks 4-8 的 Herdr 檢查 are independent of the apps list, Task 9 still checks each app for a missing agent system, and Task 10 still re-syncs `AGENTS.md` 與 `CLAUDE.md`, in case that file drifted independently of the config.
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

Write the result to `<repo-root>/.straw-boss/apps.json` (same repo-root resolution as Task 1) per `references/apps-config-schema.md`'s exact field names and shapes.

**Verification:** every app in the written config has a `name`, `dir`, and at least one `match` phrase; the coordinator did not read target-app histories, ignore files, skills, or agent instructions; every proposed optional field arrived with evidence references and was confirmed by the user or supplied directly by the user.

## Task 3: Configure work routes

Ask once, project-wide — not per app — whether to configure work routes for dispatched work. A work route maps a description such as "documentation" or "programming" to one complete worker setup. This is independent of Task 2's per-app `agentKind`: that field remains the mechanical provider fallback when no route matches.

If either root `AGENTS.md` or `CLAUDE.md` already has a `<!-- straw-boss:agent-routing:start/end -->` section, show its current routes and ask whether to keep, edit, remove, or add routes. Preserve a kept route without re-asking each field.

先讀取兩檔的 routing 區段（缺少的檔案以一行專案標題建立）；僅一檔有區段時採用它，兩檔相同時保留，兩檔不同時呈現差異由使用者選定，再同步已確認內容。寫入限於 routing markers 內，保留兩檔各自的其他內容。

For every new or edited route:

1. Get the work description used for matching.
2. Get the agent kind (`claude` or `codex`) and optional provider profile — Claude's named `--agent` preset or Codex's named `--profile` configuration.
3. Recommend model and reasoning effort. Check that provider's local config, relevant installed routing guidance, and the user's personal root `AGENTS.md` 與 `CLAUDE.md` before proposing values. Use current official guidance only when local evidence gives no clear preference. For bounded investigation, audit, or diagnosis routes, offer a lower-tier model such as Haiku or a lower-tier Codex model when it remains capable of returning an explanatory result with evidence; never trade away the evidence requirement for a binary answer.
4. For a Claude route only, ask whether to use a Claude Code native advisor and, if so, recommend its model. Sonnet with Opus is one documented pairing; availability and accepted pairings still depend on the installed Claude Code account/provider. Codex has no native advisor, so a Codex route records `advisor: none` without offering a coworker or subagent as a substitute.
5. Present the whole route and get explicit confirmation or correction before recording it. Then offer another route.

Write confirmed routes as canonical prose between the routing markers, one line per route: `<work description> → worker: kind=<kind>, profile=<profile|default>, model=<model|default>, effort=<effort|default>; advisor=<model|none>`. Keep this policy in root `AGENTS.md` 與 `CLAUDE.md`, not `apps.json`.

**Verification:** every written route was confirmed as a whole; recommendations used local preferences before current official guidance; only Claude routes can name an advisor; existing routes were presented before replacement; multiple work routes can reuse the same agent kind with different profiles/models; 結果僅寫入根目錄 `AGENTS.md` 與 `CLAUDE.md` 的 agent-routing markers 內。

## Task 4: 檢查 Herdr CLI 與服務

以 `command -v herdr` 與 `herdr status` 檢查委派依賴。缺少時回報安裝或啟動 Herdr 的需求，仍可完成本地設定與 Task 10 指引同步；待服務就緒再進行 Task 9 的 app 委派。

**Verification:** 實際觀察 CLI 與服務狀態，回報尚未滿足的委派條件。

## Task 5: 建立委派狀態目錄

以 Python `Path.home()` 解析使用者目錄，建立 `.straw-boss/dispatch/` 與 `.straw-boss/dispatch/archive/`。

**Verification:** 狀態目錄位於使用者 home。

## Task 6: 檢查目前 Herdr session

以 `$HERDR_PANE_ID` 取得目前 Herdr live agent record，核對 provider 身分。缺少 pane 時，請使用者在 Herdr session 繼續委派；本地設定與 Task 10 指引同步仍可完成。

**Verification:** 委派前已取得目前 pane 與 provider fingerprint。

## Task 7: 檢查 provider integration

執行 `herdr integration status`，核對此次 worker provider 所需的整合。若 Claude integration 缺少，說明 `herdr integration install claude` 會寫入全域 Claude hook 與 settings，取得使用者授權後安裝並核對結果。Codex 依 Herdr live record 的 provider session／terminal 身分進行驗證。

**Verification:** 需要的整合已就緒，或明確回報待完成條件。

## Task 8: 完成就緒檢查

依 CLI、服務、session 與 provider integration 的實際結果判斷能否委派。模式固定為 `herdr-pane`，就緒狀態在每次委派入口重新檢查。Task 9 有未滿足條件時，回報待執行的 app inventory／bootstrap，再完成 Task 10。

**Verification:** 設定完成與委派就緒分別回報；尚未執行的 app 工作保持未完成。

## Task 9: Offer to bootstrap a missing agent system, per app

Use Task 2's worker-reported agent-system inventory for each app. For an
unchanged configured app that has no current-run report, dispatch the same
bounded inventory rooted in that app.

以下任一條件表示已有 agent system：
`<app-dir>/AGENTS.md` 或 `<app-dir>/CLAUDE.md` 存在，或 app 的 `.agents/skills/`、`.claude/skills/`、`.claude/rules/`、`.claude/hooks/` 有專案指引。settings 本身屬於設定。

已有 agent system 的 app 記錄證據；若 `AGENTS.md` 或 `CLAUDE.md` 缺少，提議透過 `create-great-harness` 補齊缺檔並保留既有指引。兩檔齊備時繼續。完全缺少 agent system 的 app，提議建立兩個指引檔。每個 app 各自確認範圍，將已確認範圍交給 bootstrap。

`AGENTS.md` 與 `CLAUDE.md` 是 bootstrap 的必要產物；可選 hook 或 rule 依具體專案證據或已確認範圍建立。

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

## Task 10: 同步根目錄 AGENTS.md 與 CLAUDE.md

等待 Task 9 中以 repo root 為 app 的 bootstrap 完成並清理後，再寫入同一根目錄的指引檔。

讀取 `<repo-root>/AGENTS.md` 與 `<repo-root>/CLAUDE.md`；缺少的檔案先建立一行專案標題。將同一份 apps 摘要同步至兩檔。僅列 app 名稱、目錄及設定位置；各 app 的詳細政策保存在 apps.json。

```markdown
<!-- straw-boss:apps:start -->
## Managed apps (straw-boss)

api — apps/api
web — apps/web

Full config (routing, redirects, per-app rules): `.straw-boss/apps.json`.
<!-- straw-boss:apps:end -->
```

既有 markers 存在時只替換區段內容；缺少時以一個空白行分隔並附加。保留兩檔各自的區段外內容。再次執行 init 時同步這兩份摘要，並核對 Task 3 已確認的 routing 區段在兩檔一致。

**Verification:** 根目錄兩個指引檔皆存在，apps 區段與設定一致，routing 區段與 Task 3 的決定一致，區段外內容保留；根目錄 bootstrap 已完成才寫入。

## References

- `references/apps-config-schema.md` — exact `apps.json` field names, types, and how other skills read it.
- `${CLAUDE_PLUGIN_ROOT}/skills/dispatching-work/references/dispatch-mechanics.md` — Herdr 委派介面。
