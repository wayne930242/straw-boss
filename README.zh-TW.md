# straw-boss

[English](./README.md) | 繁體中文

一切由你做主。把一個任務或整份 backlog 交給 `boss-say`，它會選擇足以完成工作的最小迴圈：有界工作由目前 agent 直接完成，明確分支交給 subagent 平行處理，需要獨立權責或延續狀態時才協調以 app 為根目錄的 Claude Code 或 Codex CLI workroom。單一 app 裝好就能用，需要時也能協調整個 monorepo。

名字來自牧場工頭：跟牛仔一起在現場做事，不是坐辦公室發號施令。

## 為什麼

有界工作就留在有界迴圈內。當任務需要自己的 workroom，straw-boss 會讓 worker 直接以負責的 app 為根目錄，不必複製一份終究會過時的 app 脈絡摘要。Claude Code worker 會在那裡載入 app 的 `.claude/skills/` 與 `.claude/settings.json` hooks；Claude Code 與 Codex CLI worker 都會從正確的 app 目錄與本地指示開始工作。改程式、稽核、研究與故障診斷都走同一套路由。Monorepo 可用 `work-on` 做跨 app 路由，單一 app 不需要先做這層設定。完整理由見 [docs/architecture.md](docs/architecture.md)。

## 特色

- **一個入口：`boss-say`**——工作交給它，由它選 owner、執行層級、協作圖與 reality anchor。
- **最小充分迴圈**——有界工作由目前 agent 完成；明確分支平行展開；需要延續狀態的 app 工作才開獨立 workroom。
- **Claude Code 與 Codex CLI worker**——work route 可分別指定 provider、profile、model 與 effort；Claude route 也能使用原生 advisor。
- **事件驅動協調**——持久化的 checkpoint 與 terminal status 會觸發排程、交接及清理。
- **worktree 隔離**——team-mode 任務可在各自的 feature branch 平行進行。
- **跨 main agent 資源鎖**——worktree 隔不到的 port、共用 DB migration，跨 session 排隊。
- **批次自己抓步調**——backlog 做不完一個 turn，`boss-say` 自己開 `/loop`。
- **獨立 orchestrator 交接**——經你同意後，把一個 scope 移到具名的 Herdr tab；新 orchestrator 透過 `boss-say` 接手，原窗口離開該 scope。
- **herdr 隨時介入**——旁觀或加入派出的 Claude Code／Codex CLI workroom，直接在裡面回答問題。

## 需求

- Claude Code（plugins 要開），或支援 plugin 的 Codex CLI。
- Python 3，用來執行內附的生命週期與安裝腳本。
- [herdr](https://github.com/herdrdev/herdr)（建議裝，非必要）。啟用後，派出的 Claude Code 與 Codex CLI workroom 都能旁觀及加入；沒有可用的 herdr session 時，獨立 workroom 會以 headless 模式執行。

## 安裝

從 source checkout 安裝或更新這台機器上可用的所有支援 CLI，並核對實際安裝版本：

```bash
bash scripts/install.sh
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

`init` 會詢問要管理哪些 app、設定 work route、寫入 `.claude/straw-boss/apps.json`、同步 root `CLAUDE.md`，為缺少 agent system 的 app 提議建立一套，並記錄是否啟用 herdr-backed dispatch。

單一 app 的話 `init` 只是加分，裝好 plugin 就能直接用 `boss-say`。想開 herdr、設定 `forbidDirectCommit`/`localFiles` 這類選項、或設定 monorepo 多個 app，才需要跑。

## Skills

| Skill | 說明 |
|-------|-------------|
| `init` | 問要管哪些 app、寫設定、同步 root `CLAUDE.md`、設定包含 provider profile/model/effort 與可選 Claude advisor 的 work route、缺 agent system 的 app 主動提議建一套、決定要不要開 herdr |
| `boss-say` | **所有事情的入口。**為單一任務、獨立批次或 backlog 選擇 owner skill 與最小充分迴圈 |
| `handoff-orchestrator` | 經明確同意後，把一個 scope 與最小延續狀態交給新的 orchestrator tab |
| `i-am-orchestrator` | 依狀態事件維持協調迴圈；worker 與你負責 reality anchor 內的工作細節 |
| `work-on` | 把請求對應到某個 app，處理 legacy redirect |
| `dispatching-work` | 內部派工機制——選派工方式並解析完整 work route（provider/profile/model/effort，加上僅 Claude 支援的原生 advisor）、寫指令、實際派工、列出/收尾既有派工 |
| `choosing-graph` | 工作開始前先定分工圖（single-loop、sub-agent 扇出／扇入、orchestrator-worker）與 reality anchor（testing、pseudo-human、human、對抗性審查）；anchor 只定類別和檢查點，裡面用什麼接縫、哪些案例仍由做事的 agent 和你決定 |
| `shipping-task` | 依你怎麼認定這份工作決定 git 生命週期——team-mode（worktree → develop → MR → merge → archive）或 solo-mode（直接 commit）、派工、commit 和推送自己的 feature branch 都自由，merge 前（以及推到該分支以外的任何 push 前）才找你授權 |
| `peeking-work` | 唯讀看一個派工現在在做什麼，不加入、不打斷 |
| `notifying-main-agent` | 派出去的 agent 用來聯絡 main agent、回報或問純資訊性問題 |
| `asking-peer-agents` | 讓一個派出任務向另一個任務詢問實際進度或結論 |
| `bringing-coworker` | 把一位 Claude Code 或 Codex CLI coworker 帶進互動式 worker 的同一個 Herdr tab 與 worktree |
| `create-great-harness` | 幫沒有 agent system 的 app 建一套精簡版——以證據為基礎的 `CLAUDE.md`，以及由確認範圍或專案證據支持的可選 hook／rule |
| `inspecting-app` | 解析目標 app，透過最小充分迴圈完成附證據的規則稽核 |
| `investigating-app` | 解析目標 app，透過最小充分迴圈解釋現況並附上證據 |
| `troubleshooting-app` | 一般故障在同一個 `shipping-task` 迴圈內連續診斷並修復；只有整合診斷必須先提供證據以安排後續工作時，才拆成獨立的前置調查 |

## 怎麼用

`init` 跑完，工作全丟給 main agent：

```
boss-say 修掉登入後導向錯的問題
boss-say 對照規則稽核 payments 模組
boss-say 把 docs/backlog.md 做掉
```

剩下由 `boss-say` 決定：哪個 skill 負責、目前 agent 能否直接完成或需要獨立 workroom、採用哪一種協作圖與 reality anchor、是單一任務還是批次，以及 backlog 是否需要 `/loop` 自行抓步調。它會說明選擇，你不同意時可用一句話覆寫。

想自己點名某個專責 skill 也行：

- 哪個 app 管這個？→ `work-on`
- 加入或打斷前先看一眼 → `peeking-work`
- 沒有 agent system 的 app，建一套精簡版 → `create-great-harness`
- 稽核現有程式碼 → `inspecting-app`
- 研究現在怎麼運作的 → `investigating-app`
- 東西壞了、原因不明 → `troubleshooting-app`

想知道現在有哪些派工在跑、或收尾一個，一樣問 `boss-say`。

## 設定

`init` 會把 managed app 與各 app 的生命週期選項寫進 `.claude/straw-boss/apps.json`。Schema：[skills/init/references/apps-config-schema.md](skills/init/references/apps-config-schema.md)。精簡 app 摘要與專案層級的 work route 則放在 root `CLAUDE.md`，讓各 app session 繼承。

app 也可以設定預設用非 `claude` 的 agent kind（`agentKind`）。完整 work route（provider profile、model、effort，以及可選的 Claude Code 原生 advisor）則是另一個專案層級政策，由 `init` 寫成 root `CLAUDE.md` 的文字說明，而不是塞進 per-app 設定。Codex route 不支援 advisor。

## 授權條款

[MIT](./LICENSE)
