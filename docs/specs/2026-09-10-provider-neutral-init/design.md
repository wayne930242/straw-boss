# 設計

沿用 scripts/dispatch_state.py 的共用模組慣例，新增 scripts/apps_config.py。read_apps_config(repo_root) 回傳 AppsConfig(path, payload, legacy)，負責路徑優先順序、讀取與 apps 陣列結構檢查。AppsConfigMissing 區分兩處皆缺少，其他讀取或格式錯誤使用 ValueError。copy-local-files.py 直接呼叫此介面。

技能透過 read-apps-config.py --repo-root 使用相同 handler。CLI 成功輸出 path、legacy、config，exit 0；兩處皆缺少 exit 3；無效 exit 1。呼叫端僅依結果處理，路徑與 fallback 複雜度留在模組中。比較僅抽出路徑函式的方案：那會讓 JSON 驗證與錯誤分類仍散落於呼叫端，因此選擇完整讀取結果。此介面只有讀取責任，init 仍負責已確認設定的寫入。

測試以 CLI 為公開介面，驗證來源路徑、設定欄位保留、優先順序、fallback、缺檔、損毀 JSON／結構／檔案型態及失效 symlink；既有 worktree 測試驗證第二個呼叫端。

init 沿用受管 marker 寫入方式，將相同 apps 與 routing 區段同步至兩個指引檔；先讀兩檔，若既有 routing 衝突則交由使用者決定。bootstrap 以 AGENTS.md 為共同內容，再寫入 CLAUDE.md；既有檔案保留原有指引。

用 CLI 測試新路徑、舊路徑、並存與無效新檔，並執行技能品質檢查。雙檔同步只限 Straw Boss 受管區段，避免覆蓋各 provider 的既有指引。
