# straw-boss

[English](./README.md) | 繁體中文

任何工作——實作、稽核、研究、故障診斷——都交給 boss，由他決定怎麼做:不需要你 app 自己那套環境的，就用一般 subagent;需要的，就派進一個「真的」待在你 app 目錄下的 session——headless 的 `claude -p`，或是能旁觀、能加入的 [herdr](https://github.com/herdrdev/herdr) pane。程式碼 commit 自由，每次 push 跟 merge 前都要你點頭授權。單一 app 的 repo 直接能用;monorepo 也會幫你路由到對的 app。

名字來自牧場工頭:跟牛仔一起在現場做事,不是坐辦公室發號施令。這個 plugin 做的事一樣——把任務交到對的人手上、對的地方,然後守在旁邊隨時解圍。

## 為什麼

app 自己的 `.claude/skills/` 和 `.claude/settings.json` hooks,只有工作目錄真的在那個 app 根目錄下才會載入——monorepo 根目錄或任何派工用的 cwd 都看不到。straw-boss 把工作直接派進真正待在那裡的 session,而不是手動維護一份規則摘要——不管是程式碼變更、稽核、研究還是故障診斷,只要那件事真的用得到這套環境都一樣。跨 app 路由(`work-on`)是加分項,不是前提。完整設計理由看 `docs/architecture.md`。

## 工作流程特色

- **只有一個入口:`boss-say`**——任何工作丟給他就好,不管大小、不管形態;規模怎麼判斷、要用哪一層執行方式,都是 boss 自己決定,不用你先挑 skill。
- **兩層執行方式,逐項判斷**——不需要你 app 自己那套環境的用一般 subagent,需要的就派進 app 目錄。
- **一個 epic,一個 boss**——整個 epic 由單一協調 session 負責,只派工不動手實作。
- **任務級 context**——每個派工都有自己的 context,只裝那一件任務要用的東西,不是整個專案。
- **worktree 隔離**——多個任務平行跑,互不干擾。
- **跨 boss 資源鎖**——worktree 隔離不到的 port、共用 DB migration,跨獨立 boss session 用檔案鎖排隊。
- **批次自己抓步調**——一個 turn 做不完的 backlog,`boss-say` 會自己開 `/loop`,空位一釋出就補下一個。
- **herdr 隨時讓人介入**——旁觀、加入,或任務中途被問問題;只要環境支援,herdr 就是預設的派工方式。

## 需求

- Claude Code,plugins 功能要開。
- [herdr](https://github.com/herdrdev/herdr)(建議裝,非必要)。沒裝的話,派出去的 agent 都跑 headless 的 `claude -p`——沒有即時畫面,任務中途也不會問你問題。裝了的話,派工一律用能旁觀、能加入的 pane。`init` 會檢查有沒有裝,讓你選要啟用還是跳過。

## 安裝

```
/plugin marketplace add https://github.com/wayne930242/straw-boss
/plugin install straw-boss@straw-boss
```

每個專案跑一次:

```
/straw-boss:init
```

`init` 會問你要納管哪些 app(先掃一輪常見的 monorepo 結構當起點),寫進 `.claude/straw-boss/apps.json`,同步一段納管範圍摘要進專案根目錄的 `CLAUDE.md`,對沒有 `CLAUDE.md` 也沒有 `.claude/` 的 app 主動提議建立一套精簡的 agent system,另外也會問你要不要在這台機器啟用 herdr。

單一 app 的 repo,`init` 只是錦上添花,不是前提——plugin 一裝好,`boss-say` 就能直接用,repo root 本身會被當成唯一的 app。想啟用 herdr、設定 `apps.json` 的個別選項(`forbidDirectCommit`、`localFiles` 等)、或設定 monorepo 的多個 app,才需要跑 `init`;不跑也能直接開始把工作交給 boss。

## Skills

| Skill | 說明 |
|-------|-------------|
| `init` | 一次性設定:問要納管哪些 app、寫設定檔、同步 root `CLAUDE.md`、對缺 agent system 的 app 主動提議建立;決定要不要啟用 herdr |
| `boss-say` | **所有事情的入口。**判斷規模,也逐項判斷執行層——一般 subagent,還是派進 app 的 agent——再交給對應的專責 skill 或自己的批次機制 |
| `work-on` | 把請求對應到某個已設定的 app,處理 legacy redirect |
| `dispatching-work` | 內部派工機制,由 `boss-say` 的各專責 skill 驅動——選派工方式(herdr 可用就用 `herdr-pane`,不可用才退回 `claude-p`)、寫派工指令、實際派工、列出/收尾既有派工 |
| `shipping-task` | 決定 git 生命週期(worktree → develop → MR → merge → archive,或直接 commit)、派工單一任務、commit 自由,每次 push/merge 前找你授權;由 `boss-say` 驅動 |
| `peeking-work` | 唯讀查看某個派工目前在做什麼——herdr pane 的輸出,或 `claude-p` 的 transcript tail——不加入、不打斷 |
| `notifying-boss` | 派出去的 agent 用來聯絡 boss、回報或問純資訊性問題——優先用 herdr,`SendMessage` 當備援 |
| `create-great-harness` | 幫沒有 `CLAUDE.md` 也沒有 `.claude/` 的 app 建一套精簡 agent system——一份 `CLAUDE.md` 加一個經過 pipe-test 驗證的 guard hook |
| `inspecting-app` | 對應出目標 app,再跑你自己的規則/慣例稽核 skill——依 `boss-say` 的判斷,單獨做或派工;由 `boss-say` 驅動 |
| `investigating-app` | 對應出目標 app,再跑你自己的研究型 skill——同一套判斷,單獨做或派工;由 `boss-say` 驅動 |
| `troubleshooting-app` | 診斷回報的故障——app 程式碼還是基礎設施出包,單獨做或派工——再把修正交回 `boss-say` |

## 怎麼用

`init` 跑完之後,任何工作都交給 boss——實作、稽核、研究、故障診斷,一件或一整份 backlog 都一樣:

```
boss-say 修掉登入後導向錯的問題
boss-say 對照我們的規則稽核 payments 模組
boss-say 把 docs/backlog.md 這批做掉
```

剩下的 `boss-say` 自己決定:逐項判斷執行層——單獨做,還是派進 app;也判斷規模形態——單一項目走對應的專責 skill,多個獨立項目變成有並行上限的批次,一個 turn 做不完的批次就自己開 `/loop` 抓步調。兩者都不用你挑——它會講它選了什麼,你不同意再喊停就好。

上面每個專責 skill 也都能直接點名呼叫,如果你想自己觸發:

- 只是想知道某個請求歸哪個 app 管 → `work-on`
- 想在加入或打斷之前先看某個 agent 做到哪 → `peeking-work`
- 幫沒有 agent system 的 app 建一套精簡版 → `create-great-harness`(`init` 也會主動提議)
- 對照規則稽核現有程式碼 → `inspecting-app`
- 研究目前行為,沒有規則或故障要查 → `investigating-app`
- 東西壞了,原因不明 → `troubleshooting-app`(先診斷,再把修正交回 `boss-say`)

想問目前有哪些派工在跑,或收尾某一個,一樣經過 `boss-say`——它會直接讀 `dispatching-work` 自己的追蹤紀錄。

## 設定

專案專屬的東西——有哪些 app、怎麼路由、各 app 的 git 生命週期差異、legacy redirect、跨 app 協調——全部放在 `init` 寫的 `.claude/straw-boss/apps.json` 裡。Schema 見 [skills/init/references/apps-config-schema.md](skills/init/references/apps-config-schema.md)。`init` 也會把精簡摘要(只有名稱和目錄)同步進專案根目錄的 `CLAUDE.md`,因為 monorepo 的 root `CLAUDE.md` 會被每個巢狀 app 的 session 繼承,不是只有 straw-boss 自己讀。

## 授權條款

[MIT](./LICENSE)
