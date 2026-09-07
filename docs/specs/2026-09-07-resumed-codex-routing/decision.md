# 恢復 Codex session 的派工路由

Alignment：修復 MP-2356 恢復 session 後無法回報完成的問題，讓同一 session 能接續派工通訊。

| Question | Answer | Basis | Status |
|---|---|---|---|
| 失效條件 | Herdr 恢復後 terminal_id 改變，派工只保存舊 terminal_id | MP-2356 progress、現行 Herdr agent list、dispatch_session.py 重現 | grounded |
| 接續身分 | 保存並驗證 Codex agent_session.value；terminal_id 保留給舊版相容 | Herdr 現已提供 Codex session；原規格針對 0.8.0 無此欄位 | grounded |
| 舊記錄修復 | 透過明確接續命令，輸入原 session 證據並核對 live session、pane 與執行者 | 舊 instruction 的 session_id 為 null，無從自動證明身分 | grounded |
| 變更邊界 | 共用身分判定、launch/write 保存、roll-call/recovery 一致性、可追溯的單筆修復 | 使用者要求調查及重構修正 Straw Boss | confirmed |

不變更 MP-2356 實作、合併決策或其他派工的狀態。
