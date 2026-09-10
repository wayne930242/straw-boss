# 驗證

| Requirement | Evidence | Result |
|---|---|---|
| 新設定位置與保留舊設定的 init 遷移規則 | 檢閱 init Task 1／2 與 apps-config-schema：確認後寫入新位置，保留完整欄位與舊檔，讀回核對。此項為技能指引審查。 | pass |
| 新路徑優先與舊版 fallback | test_apps_config.py 的 CLI 案例及 test_copy_local_files.py 的 git worktree 案例：新舊並存、新檔無效、舊檔單獨存在皆符合契約。 | pass |
| AGENTS.md 辨識、補齊與同步 | 檢閱 init Task 3／9／10 與 bootstrap Task 3：已有任一指引檔會保留；缺檔提出補齊；受管 apps／routing 區段同步兩檔，保留區段外內容。品質測試確認拒絕 herdr 仍抵達同步步驟。此項為技能指引審查。 | pass |
| 共用 handler 與錯誤分類 | CLI 6 項測試涵蓋未知欄位保留、來源資訊、缺檔 exit 3、格式與讀取錯誤 exit 1；copy-local-files.py 的 12 項測試驗證 Python 呼叫端。 | pass |
| 讀取端與現行文件一致 | init、work-on、plan-mechanics 改用 schema 的共用 handler；README 與架構說明採新位置並記錄舊版相容；技能品質測試 60 項通過。 | pass |

前後證據：新路徑 worktree 測試在原讀取器下失敗，修改後通過；handler CLI 測試在介面建立前失敗，建立後通過。git diff --check 通過。

限制：未執行真人互動的完整 init／bootstrap；指引寫入與同步的證據為技能文本審查，並非實際 agent 執行結果。使用者已授權 bump、commit、push、install；交付結果另由本次發布回報核對。

發布前驗證（0.18.42）：完整 unittest suite 353 項通過（150.915 秒）；plugin manifest validator 與四個修改技能的 quick_validate 通過；git diff --check 通過。未發現本次範圍內的發布阻擋問題。
