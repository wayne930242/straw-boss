# straw-boss

[English](./README.md) | 繁體中文

一切由你做主。你說一聲，`boss-say` 立刻幫你派工——分給最適合的 agent：簡單的丟一般 subagent，要動到 app 自己環境的就派進那個 app 目錄下的 session（headless 的 `claude -p`，或能旁觀、能加入的 [herdr](https://github.com/herdrdev/herdr) pane）。單一 app 直接用，monorepo 也接得住跨 app 協作。你隨時看得到現在在發生什麼事。

名字來自牧場工頭：跟牛仔一起在現場做事，不是坐辦公室發號施令。

## 為什麼

app 自己的 `.claude/skills/`、`.claude/settings.json` hooks，只有 session 真的待在那個 app 目錄下才會載入。straw-boss 把工作派進真正待在那裡的 session，不用手動維護一份規則摘要——不管是改程式碼、稽核、研究還是抓故障都一樣。跨 app 路由（`work-on`）是加分，不是門檻。完整理由看 `docs/architecture.md`。

## 特色

- **一個入口：`boss-say`**——工作丟給他，規模跟怎麼派都是他決定，你不用先挑 skill。
- **兩層執行**——不需要 app 環境的用 subagent，需要的就派進去，逐項判斷。
- **一個 epic，一個 main agent**——一個 session 統籌整個 epic，只派工不動手。
- **worktree 隔離**——平行任務互不干擾。
- **跨 main agent 資源鎖**——worktree 隔不到的 port、共用 DB migration，跨 session 排隊。
- **批次自己抓步調**——backlog 做不完一個 turn，`boss-say` 自己開 `/loop`。
- **herdr 隨時介入**——旁觀、加入、中途回答問題；環境支援就是預設。

## 需求

- Claude Code，plugins 要開。
- [herdr](https://github.com/herdrdev/herdr)（建議裝，非必要）。沒裝就跑 headless `claude -p`——看不到即時畫面，也不能中途問你問題。`init` 會問你要不要裝。

## 安裝

```
/plugin marketplace add https://github.com/wayne930242/straw-boss
/plugin install straw-boss@straw-boss
```

每個專案跑一次：

```
/straw-boss:init
```

`init` 問你要管哪些 app、寫進 `.claude/straw-boss/apps.json`、同步進 root `CLAUDE.md`，缺 agent system 的 app 主動提議建一套，順便問要不要開 herdr。

單一 app 的話 `init` 只是加分，裝好 plugin 就能直接用 `boss-say`。想開 herdr、設定 `forbidDirectCommit`/`localFiles` 這類選項、或設定 monorepo 多個 app，才需要跑。

## Skills

| Skill | 說明 |
|-------|-------------|
| `init` | 問要管哪些 app、寫設定、同步 root `CLAUDE.md`、缺 agent system 的 app 主動提議建一套、決定要不要開 herdr |
| `boss-say` | **所有事情的入口。**判斷規模、逐項判斷要單獨做還是派工，交給對應的專責 skill 或自己的批次機制 |
| `work-on` | 把請求對應到某個 app，處理 legacy redirect |
| `dispatching-work` | 內部派工機制——選派工方式（herdr 可用就用 `herdr-pane`，不可用才退回 `claude-p`）、寫指令、實際派工、列出/收尾既有派工 |
| `shipping-task` | 決定 git 生命週期（worktree → develop → MR → merge → archive，或直接 commit）、派工、commit 自由，push/merge 前找你授權 |
| `peeking-work` | 唯讀看一個派工現在在做什麼，不加入、不打斷 |
| `notifying-main-agent` | 派出去的 agent 用來聯絡 main agent、回報或問純資訊性問題 |
| `create-great-harness` | 幫沒有 agent system 的 app 建一套精簡版——一份 `CLAUDE.md` 加一個 guard hook |
| `inspecting-app` | 對應出 app，跑你自己的規則稽核 skill——單獨做或派工 |
| `investigating-app` | 對應出 app，跑你自己的研究 skill——單獨做或派工 |
| `troubleshooting-app` | 診斷故障——app 程式碼還是基礎設施，單獨做或派工——再把修正交回 `boss-say` |

## 怎麼用

`init` 跑完，工作全丟給 main agent：

```
boss-say 修掉登入後導向錯的問題
boss-say 對照規則稽核 payments 模組
boss-say 把 docs/backlog.md 做掉
```

剩下 `boss-say` 決定：單獨做還是派工、單一任務還是批次、要不要開 `/loop`。它會講它選了什麼，你不同意就喊停。

想自己點名某個專責 skill 也行：

- 哪個 app 管這個？→ `work-on`
- 加入或打斷前先看一眼 → `peeking-work`
- 沒有 agent system 的 app，建一套精簡版 → `create-great-harness`
- 稽核現有程式碼 → `inspecting-app`
- 研究現在怎麼運作的 → `investigating-app`
- 東西壞了、原因不明 → `troubleshooting-app`

想知道現在有哪些派工在跑、或收尾一個，一樣問 `boss-say`。

## 設定

app、路由、legacy redirect、跨 app 協調——全在 `init` 寫的 `.claude/straw-boss/apps.json`。Schema：[skills/init/references/apps-config-schema.md](skills/init/references/apps-config-schema.md)。root `CLAUDE.md` 也會同步一份精簡摘要，因為每個 app session 都會繼承到 monorepo 的 root `CLAUDE.md`。

## 授權條款

[MIT](./LICENSE)
