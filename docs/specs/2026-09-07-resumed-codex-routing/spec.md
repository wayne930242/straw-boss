Status: approved
Approved at: 2026-09-07
Approved from: 使用者「好，以最佳化方式修復（程式碼越來越複雜了，請考慮重構）」

# 可觀察契約

1. 新 Codex 派工保存 Herdr 提供的 session id；相同 pane、provider 與 session 在 terminal 改變後仍能送訊息、回報狀態。
2. 已保存 session 的派工遇到不同或缺失 session 時拒絕通訊，即使 terminal 相同。舊版無 session 記錄維持 exact terminal 檢查。
3. roll-call 與 recovery 使用同一身分規則，避免把恢復後仍存在的 worker 誤判為已關閉。
4. 單筆接續命令用原 session 證據核對目前 caller 與 worker，再補登 session 與新終端，保留稽核資料及原 launch receipt/contract；不依名稱、cwd 或 pane 相同直接認領。
5. MP-2356 路由恢復後由原 worker 重報完成；協調端核對交付證據。

Reality anchor：testing。先重現 terminal 更換造成回報拒絕及錯誤 closed 判斷，再跑 public CLI 回歸、拒絕案例、完整測試；最後驗證原 worker 的真實回報。

適用專案約定：精簡且局部的修改、來源先讀、保留使用者變更、驗證後聲明結果。舊規格：../2026-08-27-codex-herdr-identity/spec.md。
