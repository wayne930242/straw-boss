Status: approved
Approved at: 2026-09-07
Approved from: 使用者選擇「派工前登記＋stance 一行（建議）」

# 可觀察契約

1. 在 herdr pane 內執行 `register-orchestrator.py --scope "<一句話>"`，會以自身 provider 指紋為鍵寫入 `~/.straw-boss/orchestrators/`，記錄 agent kind、session／terminal 指紋、pane id、herdr agent 名稱、cwd、scope 與時間，並印出自己的記錄加上目前存活的其他 orchestrator。
2. 同一 session 重新登記只更新既有記錄（pane、名稱、cwd、scope、updated_at），不產生第二筆。
3. `HERDR_PANE_ID` 缺失、herdr 沒有該 pane 的活躍 agent、或 agent kind 非 claude／codex 時拒絕登記並說明原因。
4. scope 必須非空、單行、至多 200 字元。
5. `register-orchestrator.py --list` 只讀取目錄：指紋在 `herdr agent list` 比對得到的記錄標 `live: true` 並顯示目前 pane，比對不到的標 `live: false` 且檔案保留。
5a. 登記時順帶清掉「已經沒有活躍 agent 且 `updated_at` 超過 7 天」的記錄，並在輸出的 `retired` 列出；該記錄的 ledger 保留。目錄因此維持在「現在誰在協調」的可讀範圍。
6. `send-orchestrator-message.py --to <名稱或 pane> --intent inform|question|answer --message "<delta>" [--ref …] [--in-reply-to <id>]` 送出的 envelope 形如 `[orchestrator <intent> id=<uuid> from=<名稱> pane=<發送端 herdr pane id>[ in-reply-to=<id>][ refs=[…]]] <訊息>`。
7. 發送端必須已登記、目前 pane 與其記錄的 live session 相符，否則拒絕送出。
8. 收件端以指紋在 live agent list 解析目前 pane；身分不符時拒絕送出，完全找不到活躍 agent 時把訊息本文記入收件端 ledger 標為未送達，並以警告回報。
9. `--intent answer` 需要 `--in-reply-to`，且該 id 必須是收件端先前送給本 session 的 question；否則拒絕。
10. 訊息本文沿用既有的 delta 規則：至多兩句，細節走 `--ref`；成功送出後寫入收件端記錄旁的 `.messages.jsonl` ledger。
11. 新 skill `contacting-orchestrators` 說明登記、查目錄、送訊息與收到訊息後的回覆路徑；`dispatching-work` Task 1 在解析自身可達性時登記，注入的 orchestrator stance 有一行指向這條路。

# 相容性與非目標

不變更 dispatch instruction schema、worker peer 通訊、handoff 流程與既有 skill 的職責邊界。orchestrator 之間的訊息只承載事實、問題與答案，指示與授權仍留在使用者與各自 worker 的對話中。目錄是機器本地的，不跨主機同步；沒有 herdr 的 headless session 不登記。

# 適用標準

精簡且局部的修改、重用既有身分與傳輸機制、來源先讀、驗證後才聲明結果（`~/.claude/projects/weihung-user-claude/shared/engineering.md`）。身分判定沿用 `scripts/dispatch_session.py` 的 `agent_matches_identity`；缺席不作為刪除授權，沿用 `scripts/roll-call.py` 的原則。

# Reality anchor

testing：以 `tests/` 既有的假 herdr fixture 驗證公開 CLI 的真實行為——登記與更新、存活與失效判定、envelope 帶出發送端 pane id、身分不符與收件端消失的兩種拒絕路徑、answer 的來源檢查——外加既有 skill 品質測試。Checkpoint：整包 `python -m pytest tests` 綠燈後回報。
