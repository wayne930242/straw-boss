# 設計

保留 instruction.mode 欄位與 --mode herdr-pane 呼叫相容性，限制為唯一支援模式。dispatch-task 在寫入前拒絕其他模式；render_dispatch_contract 移除無頭分支。刪除 run-headless-dispatched-agent.py 與專用失敗重派分支，plan 的正常依賴判定維持既有介面。

installer 保持獨立；Herdr 檢查集中在委派入口。init 將原 capability／enable 階段改為服務、session 與 provider integration 檢查。沿用 Herdr launcher 的服務及身分驗證；狀態／歸檔腳本保持可在服務故障時處理已保存資料。

將無頭專用測試改為模式拒絕測試；保留 Herdr 共用案例與清理邊界，保留 installer 測試以驗證安裝獨立於 Herdr。使用 writing-great-skills 與 codebase-design 的單一權威與介面規則。
