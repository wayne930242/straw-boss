# straw-boss

[English](./README.md) | 繁體中文

Claude Code plugin，把實作工作丟給一個「真的」待在 app 目錄下執行的 session：可能是 headless 的 `claude -p`，也可能是可以旁觀、能加入的 [herdr](https://github.com/herdrdev/herdr) 互動 pane。git 流程走標準化生命週期，commit/push/merge 前都要經過你授權。單一 app 的 repo 直接能用；如果是 monorepo，會先幫你把請求路由到正確的 app。

名字取自牧場用語：straw boss 是跟牛仔一起在現場幹活的工頭，不是坐辦公室發號施令的那種。這個 plugin 做的事也一樣——把每件任務交到對的人手上、對的地方，然後留在附近隨時能幫忙解圍。

## 為什麼要這麼做

app 自己的 `.claude/skills/` 和 `.claude/settings.json` hooks，只有 session 的工作目錄真的落在那個 app 根目錄底下才會載入。換成別處跑的 session——monorepo 根目錄，或任何拿來派工用的 cwd——就算 path-scoped rules 跟巢狀 `CLAUDE.md` 吃得到，這些 skills/hooks 照樣看不見。straw-boss 直接解決這個問題：把工作本身派到一個真正落在目標目錄裡的 session 去跑，而不是手動維護一份「這個 app 規則寫了什麼」的摘要。這才是整個 plugin 的核心；跨 app 路由（`work-on`）只是疊加上去的加分功能，不是用其他部分的前提。完整設計理由看 `docs/architecture.md`。

能撐住這套流程的幾個關鍵設計：

- **單一協調者。** 一個協調用的 session 負責讓整個工作流保持順暢，它自己不動手做實作，只負責派工。
- **context 依工作量分配。** 每個派出去的 session 都有自己獨立的 context，只裝那一件任務要用的東西，不是整個專案。
- **worktree 隔離做平行處理。** 多個任務可以同時跑，各自用自己的 git worktree，互不干擾。
- **用 `/loop` 處理連續批次工作。** `boss-say` 可以讓一批獨立任務跨很多個 turn 跑，靠 `/loop` 自己抓步調，不用把一個 turn 硬撐很久。
- **herdr 讓人可以隨時介入。** 派工過程能旁觀、能加入，任務卡住需要人的時候會被問問題——在真正需要人的地方才插手。

## 需求

- Claude Code，plugins 功能要開。
- [herdr](https://github.com/herdrdev/herdr)（建議裝，非必要）。沒裝的話每次派工都跑成 headless 的 `claude -p`——沒有即時畫面，任務中途也不會問你問題。裝了之後 straw-boss 能開出互動式 pane，你可以旁觀、加入，任務卡住時也會被問問題。`init` 會檢查有沒有裝，讓你決定要啟用還是先跳過、繼續只用 `claude-p`。

## 安裝

```
/plugin marketplace add https://github.com/wayne930242/straw-boss
/plugin install straw-boss@straw-boss
```

每個專案跑一次 `init`：

```
/straw-boss:init
```

`init` 會問你要納管哪些 app（先掃一輪常見的 monorepo 結構當起點），寫進 `.claude/straw-boss/apps.json`，再把納管範圍的摘要同步進專案根目錄的 `CLAUDE.md`。另外也會問你要不要在這台機器上啟用 herdr 派工。

## Skills

| Skill | 說明 |
|-------|-------------|
| `init` | 一次性設定：問要納管哪些 app、寫設定檔、同步 root `CLAUDE.md`；決定要不要啟用 herdr |
| `work-on` | 把請求對應到某個已設定的 app，處理 legacy redirect；把實作請求交給派工 |
| `dispatching-work` | 選派工模式（`claude-p` / `herdr-pane`）、寫派工指令、實際派工、列出/收尾既有派工 |
| `shipping-task` | 決定 git 生命週期（worktree → develop → MR → merge → archive，或直接 commit）、派工單一任務、每次 commit/push/merge 前找你授權 |
| `boss-say` | 在固定並行上限下跑一批獨立任務，一有空位就補下一個；可以一次跑完，也可以搭配 `/loop` 反覆調用 |
| `inspecting-app` | 對應出目標 app，交給你自己的規則/慣例稽核 skill（唯讀，不派工） |
| `investigating-app` | 對應出目標 app，交給你自己的研究型 skill（唯讀，不派工） |
| `troubleshooting-app` | 診斷回報的故障——app 程式碼還是基礎設施出包——再交給 `shipping-task` 修 |

## 怎麼用

`init` 跑完之後，看你在做什麼就觸發對應的入口 skill：

- 開始實作 → `shipping-task`（內部會先呼叫 `work-on`，再派工）
- 處理一批獨立任務 → `boss-say`（一次跑完，或 `/loop boss-say ...` 讓它自己抓步調跨多個 turn 跑）
- 只是想知道某個請求歸哪個 app 管 → `work-on`
- 對照規則稽核現有程式碼 → `inspecting-app`
- 研究目前行為，沒有規則或故障要查 → `investigating-app`
- 東西壞了，原因不明 → `troubleshooting-app`
- 看目前有哪些派工在跑，或是收尾一個 → `dispatching-work`

## 設定

所有專案專屬的東西——有哪些 app、怎麼路由、各 app 的 git 生命週期差異、legacy redirect、跨 app 協調要注意什麼——全部放在 `init` 寫的 `.claude/straw-boss/apps.json` 裡。Schema 在 [skills/init/references/apps-config-schema.md](skills/init/references/apps-config-schema.md)。`init` 也會把一份精簡摘要（只有名稱和目錄）同步進專案根目錄的 `CLAUDE.md`——刻意寫得很精簡，因為 monorepo 的 root `CLAUDE.md` 會被每個巢狀 app 的 session 繼承到，不是只有 straw-boss 自己會讀。

## 授權條款

[MIT](./LICENSE)
