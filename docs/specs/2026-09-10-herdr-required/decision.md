# Herdr 必要需求

| Question | Answer | Basis | Status |
|---|---|---|---|
| 支援哪種委派模式？ | 僅 Herdr pane，移除無頭執行與續跑。 | 使用者明確要求。 | confirmed |
| 缺少 Herdr？ | 安裝保持獨立；init／dispatch 檢查服務與 session，回報就緒步驟。 | 使用者接受將必要檢查放在委派入口的建議。 | grounded |
| 舊 capability 選擇？ | 不再讀取模式偏好，init 不再詢問是否啟用 Herdr。 | 單一模式取代選項。 | grounded |
| 舊任務資料？ | 保留終態資料的歸檔能力；執行中的任務仍需終態證據，移除以程序退出代替狀態的例外。 | 保留資料且統一清理契約。 | grounded |

維持單一迴圈與既有 Herdr 身分、狀態、checkpoint、清理機制。此次不重新設計 app routing。
