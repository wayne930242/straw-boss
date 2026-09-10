Status: approved
Approved at: 2026-09-10
Approved from: 使用者「ok，好吧，那差別真的很大，修吧」，接受移除無頭委派並將 Herdr 檢查限於委派入口的評估建議。

# 契約

1. dispatch 僅建立 herdr-pane 指令，舊模式明確拒絕；移除無頭 runner 與專用重試選項。
2. 安裝與讀取／整理本地狀態獨立運作；委派入口與 init 驗證 Herdr 服務與目前 session，回報缺少條件，不再提供模式選擇或依賴 capability.json。
3. checkpoint 由 worker pane 接受使用者回覆，協調者使用 reply-to-worker；執行中任務缺少終態紀錄時保持未清理。
4. README、現行技能、架構文件與生成 contract 一致描述必要需求；歷史決策文件保留。
5. Claude 與 Codex 的 Herdr launch、回報、復原與清理測試保持通過。

Reality anchor：公開 CLI 拒絕舊模式與 Herdr 啟動前置條件案例，完整 unittest suite，以及現行指引檢閱。提交、推送、安裝另依使用者指示進行。
