# straw-boss

[English](./README.md) | 繁體中文

一個 Claude Code plugin，把實作工作派工到一個真正 cwd 在該 app 自身目錄下的 session 裡執行——可以是 headless 的 `claude -p` process，也可以是互動式、可以旁觀與加入的 [herdr](https://github.com/herdrdev/herdr) pane——並搭配標準化的 git 生命週期，每次 commit/push/merge 前都要經過授權關卡。單一 app 的 repo 也能直接使用；如果是 monorepo，還會先把每個請求路由到正確的 app。

這個名字取自牧場用語：straw boss 是跟牛仔們一起在現場工作的工頭，不是坐辦公室的。這正是這個 plugin 的工作方式——把每個任務交到對的人手上、對的地方，並且待在夠近的距離隨時解圍。

## 為什麼需要它

一個 app 自己的 `.claude/skills/` 和 `.claude/settings.json` hooks，只有在 session 的工作目錄就是該 app 自身的根目錄時才會載入。從別處運作的 session——不管是 monorepo 根目錄，還是任何派工用的 orchestrating cwd——即使 path-scoped rules 和巢狀 `CLAUDE.md` 檔案能觸及到它，也永遠看不到這些 skills/hooks。straw-boss 的解法是把工作本身派工到一個真正生活在目標目錄下的 session 裡，而不是手動維護一份「該 app 規則說了什麼」的摘要。這才是這個 plugin 的核心——跨 monorepo 多個 app 的路由（`work-on`）只是疊加在上面的額外一層，不是使用其餘功能的前提。完整設計理由見 `docs/architecture.md`。

## 需求

- Claude Code，且已啟用 plugins。
- [herdr](https://github.com/herdrdev/herdr)（建議安裝，非必要）。沒有它的話，每次派工都會跑成 headless 的 `claude -p` process——沒有即時 pane，也不會被任務中途詢問。裝了它之後，straw-boss 就能開出一個你可以旁觀、加入、並在任務中途被詢問問題的互動式 pane。`init` 會檢查它是否存在，讓你決定要啟用還是跳過、繼續只用 `claude-p`。

## 安裝

```
/plugin marketplace add https://github.com/wayne930242/straw-boss
/plugin install straw-boss@straw-boss
```

然後每個專案跑一次 `init`：

```
/straw-boss:init
```

`init` 會詢問你要納管哪些 apps（先掃描常見的 monorepo 結構作為起點），寫入 `.claude/straw-boss/apps.json`，並把一段納管範圍的摘要同步進專案根目錄的 `CLAUDE.md`。它也會另外詢問是否要在這台機器上啟用 herdr 派工。

## Skills

| Skill | 說明 |
|-------|-------------|
| `init` | 一次性設定：詢問要納管哪些 apps、寫入設定檔、同步 root `CLAUDE.md`；決定是否啟用 herdr 派工 |
| `work-on` | 把請求解析成其中一個已設定的 app，套用任何 legacy redirect；把實作請求交給派工 |
| `dispatching-work` | 選擇派工模式（`claude-p` / `herdr-pane`）、寫派工指令、實際派工、列出/收尾既有派工 |
| `shipping-task` | 決定 git 生命週期（worktree → develop → MR → merge → archive，或直接 commit）、派工單一任務，並在每次 commit/push/merge 前取得使用者授權 |
| `boss-say` | 在固定的並行上限下驅動一批獨立任務，一有空位就補下一個；可以一次跑完，也可以透過 `/loop` 反覆調用 |
| `inspecting-app` | 解析出目標 app，交給你自己的規則/慣例稽核 skill（唯讀，不派工） |
| `investigating-app` | 解析出目標 app，交給你自己的研究型 skill（唯讀，不派工） |
| `troubleshooting-app` | 診斷回報的故障——app 程式碼還是基礎設施——然後交給 `shipping-task` 修復 |

## 使用方式

`init` 跑完之後，依你正在做的事觸發對應的入口 skill：

- 開始實作某件事 → `shipping-task`（內部會呼叫 `work-on`，再派工）
- 處理一批獨立任務 → `boss-say`（一次跑完，或用 `/loop boss-say ...` 讓它跨多個 turn 自行調配步調）
- 只是想知道某個請求屬於哪個 app → `work-on`
- 對照規則稽核既有程式碼 → `inspecting-app`
- 研究目前行為，沒有規則或故障要查 → `investigating-app`
- 有東西壞了，原因未知 → `troubleshooting-app`
- 查看目前有哪些派工在跑，或收尾一個 → `dispatching-work`

## 設定

所有專案專屬的東西——有哪些 app、怎麼路由到它們、各 app 的 git 生命週期差異、legacy redirect、跨 app 協調的指引——都放在 `init` 寫入的 `.claude/straw-boss/apps.json` 裡。Schema 見 [skills/init/references/apps-config-schema.md](skills/init/references/apps-config-schema.md)。`init` 也會把一份精簡的納管範圍摘要（只有名稱和目錄）同步進你專案根目錄的 `CLAUDE.md`——刻意寫得很精簡，因為 monorepo 的 root `CLAUDE.md` 會被每個巢狀 app 的 session 繼承，不只是 straw-boss 自己會讀到。

## 授權

[MIT](./LICENSE)
