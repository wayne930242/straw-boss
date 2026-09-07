# 驗證

| Requirement | Evidence | Result |
|---|---|---|
| 同 session 換 terminal 可接續 | tests/test_resumed_codex_identity.py：restart、public status CLI、launcher capture 案例 | pass |
| session 相異或缺失時拒絕傳訊 | 同檔 wrong/missing session、legacy exact terminal、provider 案例 | pass |
| roll-call 與 recovery 保留真正存活的 session | missing-session 不代報、moved-session 顯示 routing-mismatch、legacy mismatch 不作關閉證據 | pass |
| 單筆舊路由修復可追溯 | public rebind CLI：caller process、原 rollout 證據、Unicode、batched launch、拒絕不落盤、receipt/contract 保留 | pass |
| 原 worker 真實重報 | archive/moldplan-frontend-2--mp-2356.status.json：2026-09-07T06:44:50Z done；原兩端 session 回報與 reply 均成功 | pass |

- 原始回歸曾有 4 項失敗；既有基線 52 tests OK。
- 完整測試：`python3 -m unittest discover -s tests -q`，296 tests OK（218.239s）；日誌 `/tmp/straw-boss-routing-final-tests.log`。
- 最後加強 legacy terminal mismatch 不作關閉證據後，新增路由 suite 共 23 tests OK（7.319s）。
- `git diff --check` 通過。
- 同一獨立審查 checkpoint：missing session、moved pane、Unicode evidence、batched launch evidence 四項已修正；審查者確認 0 項未解 finding。
- MP-2356 交付已獨立核對：commit 77a4f61b519d541bfe294f685252216ebc482f28，MR !91 merged，merge f87f8d07242d45a10e3bcc191d177aebb8a882a8，CI 31306 success；worker 與已合併乾淨 worktree 已收尾、dispatch 已歸檔。

## 交付邊界

使用者已授權發布 0.18.32、commit、push 與 repository installer。真實 worker 已透過 STRAW_BOSS_PLUGIN_ROOT 指向來源版本完成驗證；遠端與安裝版本由交付流程另行核對。未重新檢查 MP-2356 的自動部署，沿用使用者的收工指示。
