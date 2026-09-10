# 驗證紀錄

| Requirement | Evidence | Result |
|---|---|---|
| 僅 Herdr 委派 | test_retired_mode_is_rejected_before_writing：舊模式 CLI 被拒絕且無指令寫入；contract 對兩個 provider 都拒絕舊模式。 | pass |
| 委派前置條件與獨立安裝／設定 | test_unavailable_herdr_keeps_dispatch_pending：不可用的 Herdr 回報錯誤，保持 pending 且沒有 launch receipt；installer 未變更，init 與 README 明述本地操作可獨立。 | pass |
| 統一 checkpoint 與清理 | contract、技能品質與既有 Herdr 狀態測試；舊模式 in-progress 無終態時拒絕歸檔，pending 可清理。完整 suite 348 項通過。 | pass |
| 現行文件一致 | 品質測試掃描現行 skill／docs／README，無無頭模式分支；六個技能 quick_validate 通過。 | pass |
| Herdr 流程回歸 | 完整 unittest suite 348 項通過（147.820 秒），涵蓋 Herdr 啟動、狀態、復原、清理與 installer。 | pass |

針對性測試：17 項 plan orchestration 與 61 項技能品質測試通過。新增 Herdr 失聯案例最初誤用已啟動 fixture，已改為 pending fixture；靜態掃描發現的剩餘舊說明已移除。

使用者已授權 bump、commit、push、install，交付版本為 0.18.43；提交、推送與安裝結果由本次發布回報核對。未執行真人互動 UAT；使用現有 fake Herdr 公開 CLI 回歸測試驗證。

最終驗證：`python3 -m unittest discover -s tests -p test_*.py` 全數通過，`git diff --check` 通過。首輪的唯一失敗是修正前已載入的 fixture；完整重跑確認消除。

## herdr 0.9.0 真實派工 UAT（2026-09-10）

環境：本機 herdr 由 0.8.2 升到 0.9.0（`herdr status`：client／server 0.9.0、protocol 22、endpoint_protocol_generation 1、endpoint_compatible yes）；claude integration hook `~/.claude/hooks/herdr-agent-state.sh` 為 v9（`herdr integration status`：current）。Straw Boss 0.18.43。受驗對象是派工 `straw-boss--herdr-090-uat`（模式 herdr-pane，協調者 pane w3:pM，worker pane w3:pN，tab w3:t6），worker 由該 pane 內的 Claude session 自行記錄。證據為 `~/.straw-boss/dispatch/straw-boss--herdr-090-uat.*` 檔案。

| 路徑 | 實際觀察 | Result |
|---|---|---|
| 協調者透過 Herdr 啟動 worker pane | `launch.json` 於 13:20:17Z 寫入，含 pane w3:pN、tab w3:t6、terminal id 與 session id；`pane_label_warning`、`session_fingerprint_warning` 皆為 null。worker 在該 pane 內以 contract 起始；契約由 SessionStart hook（`orchestrator-priming.py` 讀 `contract_path`）注入，此為依 hook 程式碼推論，派工檔案未記錄 hook 觸發。 | pass |
| worker report-progress | 13:21:06Z 呼叫成功，`.progress.jsonl` 追加一筆；此腳本只寫檔案，不經 Herdr 通知。 | pass |
| worker checkpoint（awaiting-main-agent）經 Herdr 通知協調者 | 13:21:19Z 寫入 `.status.json`（含兩個 `--ref`），腳本輸出「notified main agent through herdr」，無 herdr 錯誤；`.messages.jsonl` 記錄 to-main／status 訊息，含來源與目標 session id。 | pass |
| 協調者 reply-to-worker 抵達 worker pane | 13:21:33Z `.status.json` 追加 `resolved_by_main_agent_at` 與 `main_agent_reply`，`.messages.jsonl` 記錄 to-worker／reply 訊息；`reply-to-worker.py` 只在 `confirm_transcript_contains` 於 worker pane 逐字稿找到回覆後才寫 `resolved_by_main_agent_at`，故 13:21:33Z 的寫入即證明回覆落入 pane；未觸發 reply-retry。worker 端（本紀錄作者）在 session 內收到 `[main-agent reply]` 前綴的新一輪對話並繼續，此觀察無獨立檔案，`.progress.jsonl` 第二筆為其回報。 | pass |
| 舊版 0.8.2 已知相容性核對（協調者查證，本輪引用） | `agent prompt --wait` gate 收緊為必須觀察到 working 或 blocked：`scripts/dispatch_transport.py` 傳 `--until` 與 `--timeout 8000`（>= 5000ms gate），相容。`pane report-agent` 參數放寬：Straw Boss 不呼叫，由 claude hook v9 負責。lifecycle event 訂閱不再重播歷史：Straw Boss 排程監看為檔案式，不受影響。worker 已重讀 `dispatch_transport.py` 確認 `--until`／`--timeout 8000` 一項。 | pass（前項自驗，其餘引用） |
| 真人在 worker pane 內親自回答 checkpoint | 本輪只由協調者以 reply-to-worker 回覆；沒有真人在 worker pane 內親自輸入回覆。 | unknown（未驗證） |
| Codex worker 在 herdr 0.9.0 上的派工 | 本輪只派 Claude worker；codex hook 為 v8，未實地走過。 | unknown（未驗證） |
| 其他訊息路徑 | worker 主動 `send-dispatch-message.py --to main --intent question`、`awaiting-user-input`／`awaiting-authorization` checkpoint、協調者 `--intent inform` 推送、reply-retry 分支、worker stop-guard hook 皆未在本輪走過。 | unknown（未驗證） |
| 終態 done 與清理歸檔 | 本紀錄寫成時尚未回報終態；結果由協調者在 wrap-up 時核對。 | unknown（記錄時） |

發現：0.18.43 生成的 contract 寫「add repeatable `--ref`」適用於 live agent messages，但 `report-progress.py` 只接受 `--instruction-path` 與 `--note`，帶 `--ref` 時以 usage 錯誤退出；`report-task-status.py` 與 `send-dispatch-message.py` 接受 `--ref`。此事已於 checkpoint 交協調者接手，本輪未改動 scripts/。

本輪範圍：team-mode，分支 `uat/herdr-090-dispatch`（base main），merge 需授權。
