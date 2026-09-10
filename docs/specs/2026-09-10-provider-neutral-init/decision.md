# 初始化的跨 agent 設定

讓新專案使用 `.straw-boss/apps.json`，既有專案保有讀取相容性，並補齊 `AGENTS.md`。

| Question | Answer | Basis | Status |
|---|---|---|---|
| 設定放哪裡？ | 專案根目錄的 `.straw-boss/apps.json`，相容 `.claude/straw-boss/apps.json`。 | 使用者回覆「好」接受前述建議。 | confirmed |
| 新舊並存？ | 新路徑優先；新檔無效時回報錯誤。 | 避免讀取過期設定的實作決策。 | grounded |
| 指引檔？ | init 同步根目錄 `AGENTS.md` 與 `CLAUDE.md` 的受管區段；bootstrap 建立兩者，保留既有內容。 | 使用者指出 AGENTS.md 缺口與本次承接範圍。 | grounded |
| 讀取規則由誰負責？ | 獨立 apps_config handler，Python 與 CLI 共用。 | 使用者要求獨立 handler 並考慮舊版 fallback。 | confirmed |
| 舊檔如何處理？ | init 將確認後的設定寫入新路徑，保留舊檔供相容工具使用並報告其已被取代。 | 可逆遷移，保留既有資料。 | grounded |

範圍包含現行技能、讀取腳本、使用文件與驗證；套件發布與全域 provider 設定維持各自生命週期。
