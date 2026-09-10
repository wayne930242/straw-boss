Status: approved
Approved at: 2026-09-10
Approved from: 使用者「好」，接受上一輪提出的新路徑與舊路徑相容方向；沿用本輪已說明的 AGENTS.md 修補範圍。

# 行為契約

1. 新設定寫入 `.straw-boss/apps.json`；init 保留已確認欄位，舊檔留存並回報遷移。
2. 讀取端優先讀新路徑，僅在新路徑不存在時回退舊路徑；新檔無效時回報錯誤。
3. init 辨識 AGENTS.md 與既有 Claude 指引，bootstrap 建立 AGENTS.md、CLAUDE.md；根目錄的 apps 與 routing 區段同步兩檔，保留區段外內容。
4. 獨立 handler 統一路徑與讀取；提供 Python 介面與 CLI，回傳來源資訊，區分設定不存在與無效。
5. 現行使用文件與讀取端遵循相同契約。

採用 docs/roles.md 的最小單一迴圈，提示詞直接描述期望行為。Reality anchor：實際 CLI 暫存 git worktree 測試，以及技能指引與差異檢閱。檢查點為本地變更完成後；不代表已發布或已安裝。
