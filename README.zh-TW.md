# straw-boss

[English](./README.md) | 繁體中文

一切由你做主。把一個任務或整份 backlog 交給 `boss-say`，它會選擇足以完成工作的最小迴圈：有界工作由目前 agent 直接完成，明確分支交給 subagent 平行處理，需要獨立權責或延續狀態時才協調以 app 為根目錄的 Claude Code、Codex CLI 或 Antigravity workroom。單一 app 裝好就能用，需要時也能協調整個 monorepo。

名字來自牧場工頭：跟牛仔一起在現場做事，不是坐辦公室發號施令。

## 為什麼

有界工作就留在有界迴圈內。當任務需要自己的 workroom，straw-boss 會讓 worker 直接以負責的 app 為根目錄，不必複製一份終究會過時的 app 脈絡摘要。Claude Code worker 會在那裡載入 app 的 `.claude/skills/` 與 `.claude/settings.json` hooks；Claude Code、Codex CLI 與 Antigravity worker 都會從正確的 app 目錄與本地指示開始工作。改程式、稽核、研究與故障診斷都走同一套路由。Monorepo 可用 `work-on` 做跨 app 路由，單一 app 不需要先做這層設定。完整理由見 [docs/architecture.md](docs/architecture.md)。

## 特色

- **一個入口：`boss-say`**——工作交給它，由它選 owner、執行層級、協作圖與 reality anchor。
- **最小充分迴圈**——有界工作由目前 agent 完成；明確分支平行展開；需要延續狀態的 app 工作才開獨立 workroom。
- **Claude Code、Codex CLI 與 Antigravity worker**——work route 可分別指定 provider、profile、model 與 effort；Claude route 也能使用原生 advisor。
- **事件驅動協調**——持久化的 checkpoint 與 terminal status 會觸發排程、交接及清理。
- **worktree 隔離**——team-mode 任務可在各自的 feature branch 平行進行。
- **跨 main agent 資源鎖**——worktree 隔不到的 port、共用 DB migration，跨 session 排隊。
- **批次自己抓步調**——backlog 做不完一個 turn，`boss-say` 自己開 `/loop`。
- **獨立 orchestrator 交接**——經你同意後，把一個 scope 與它進行中的派工移到具名的 Herdr tab；新 orchestrator 透過 `boss-say` 接手，原窗口離開該 scope。
- **herdr 隨時介入**——旁觀或加入派出的 Claude Code、Codex CLI 或 Antigravity workroom，直接在裡面回答問題。

## 需求

- Claude Code（plugins 要開）、支援 plugin 的 Codex CLI，或 Google Antigravity（AGY CLI）。
- Python 3，用來執行內附的生命週期與安裝腳本。
- [Herdr](https://github.com/herdrdev/herdr)（委派必要需求）。Claude Code、Codex CLI 與 Antigravity worker 都在可查看、可加入的 Herdr pane 執行。安裝、讀取設定與整理已保存狀態可獨立執行；開始委派前須有可用的 Herdr 服務與目前 pane。

## 安裝

從 GitHub marketplace 來源安裝或更新這台機器上可用的所有支援 CLI，並核對實際安裝版本：

```bash
bash scripts/install.sh
```

只有要直接針對目前 checkout 開發時，才明確選用這台機器的本機路徑：

```bash
bash scripts/install.sh --local
```

完成後請重開既有 agent session。對應的手動指令如下。

### Claude Code

```
/plugin marketplace add https://github.com/wayne930242/straw-boss
/plugin install straw-boss@straw-boss
```

接著每個專案跑一次：

```
/straw-boss:init
```

### Codex CLI

```bash
codex plugin marketplace add wayne930242/straw-boss --ref main
codex plugin add straw-boss@straw-boss
```

開一個新的 Codex session，讓它載入剛安裝的 skills 與 hooks；Codex 詢問時，先檢查並信任 bundled hooks，然後在每個專案跑一次：

```text
$straw-boss:init
```

也可以先啟動 `codex`，再輸入 `/plugins`，以互動介面瀏覽或管理 plugin。Codex IDE extension 目前不支援 plugins。

### Antigravity (AGY CLI)

```bash
agy plugin install wayne930242/straw-boss
```

接著每個專案跑一次：

```text
/straw-boss:init
```

`init` 會詢問要管理哪些 app、設定 work route、寫入 `.straw-boss/apps.json`、同步 root `AGENTS.md` 與 `CLAUDE.md`，為缺少 agent system 的 app 提議建立一套，並檢查 Herdr 委派需求。

單一 app 的話 `init` 只是加分，裝好 plugin 就能直接用 `boss-say`。檢查 Herdr、設定 `forbidDirectCommit`/`localFiles` 這類選項、或設定 monorepo 多個 app，才需要跑。

## 怎麼用

`init` 跑完，工作全丟給 main agent：

```
boss-say 修掉登入後導向錯的問題
boss-say 對照規則稽核 payments 模組
boss-say 把 docs/backlog.md 做掉
```

剩下由 `boss-say` 決定：哪個 skill 負責、目前 agent 能否直接完成或需要獨立 workroom、採用哪一種協作圖與 reality anchor、是單一任務還是批次，以及 backlog 是否需要 `/loop` 自行抓步調。它會說明選擇，你不同意時可用一句話覆寫。

## Skills

情境對得上就直接叫該 skill；沒列到的都交給 `boss-say`。

| 想做的事 | 用 |
|-------|-------------|
| 修 bug、做功能、稽核、研究、診斷、跑整份 backlog、問現在有哪些派工、收尾派工 | `boss-say` |
| 設定 managed app 與 work route，或檢查 Herdr 是否就緒 | `init` |
| 找出請求屬於哪個 app | `work-on` |
| 不加入、不打斷，看一眼派工正在做什麼 | `peeking-work` |
| 把一個 scope 與它進行中的派工移到新的 orchestrator tab | `handoff-orchestrator` |
| 讓這個窗口接手另一個 main agent 協調的派工 | `boss-say`；只有你要求時才會接手 |
| 處理 Straw Boss 本身的協調摩擦 | `boss-assistant` |
| 幫沒有 `AGENTS.md` 或 `CLAUDE.md` 的 app 建一套精簡 agent system | `create-great-harness` |
| 在派出去的 worker 裡找一位 coworker 一起審查或協作 | `bringing-coworker` |

其餘 skill 由 main agent 與 worker 自行執行：`i-am-orchestrator`、`choosing-graph`、`dispatching-work`、`shipping-task`、`contacting-orchestrators`、`reporting-to-user`、`notifying-main-agent`、`asking-peer-agents`。
各自的職責見 [docs/architecture.md](docs/architecture.md#components)。

## 設定

`init` 會把 managed app 與各 app 的生命週期選項寫進 `.straw-boss/apps.json`。Schema：[skills/init/references/apps-config-schema.md](skills/init/references/apps-config-schema.md)。精簡 app 摘要與專案層級的 work route 則放在 root `AGENTS.md` 與 `CLAUDE.md`，讓各 app session 繼承。

app 也可以設定預設用非 `claude` 的 agent kind（`agentKind`）。完整 work route（provider profile、model、effort，以及可選的 Claude Code 原生 advisor）則是另一個專案層級政策，由 `init` 寫成 root `AGENTS.md` 與 `CLAUDE.md` 的文字說明，而不是塞進 per-app 設定。Codex route 不支援 advisor。

設定讀取優先使用 `.straw-boss/apps.json`；新路徑不存在時相容 `.claude/straw-boss/apps.json`。`init` 將確認後的舊設定寫入新路徑並保留舊檔，回報其已被取代。

## 授權條款

[MIT](./LICENSE)
