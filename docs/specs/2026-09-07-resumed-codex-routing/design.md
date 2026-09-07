# 設計

Session 身分代表同一段 provider 對話；terminal 是當次 Herdr 終端位置。兩者分開保存。

共用 seam 留在既有 dispatch_session 模組：agent_matches_identity 提供純判定；通訊驗證、closed 判定、roll-call 都呼叫它。已記錄的 session 優先且必須匹配，舊 Codex 記錄才使用 terminal。Claude registry corroboration 保持原有行為。

launcher 從同一次 live snapshot 保存 Codex worker session 與 terminal。main 可透過既有 --main-agent-session-id 傳入，launcher 亦在驗證原 terminal 後補登現行 session。launch receipt 與 contract 保留不可變。

rebind-dispatch.py 是單筆顯式修復入口：協調端提供原始 main/worker session 與證據路徑，核對 caller process、已保存身分及兩端 live session；一次原子寫入 instruction 與內嵌稽核資料，不傳訊息也不更改任務狀態。原 session 缺失的舊記錄直接讀取 --ref 提供的原始 rollout：核對 session_meta、launch 前協調端的派工回執，以及 worker 初始 developer context 的 contract 路徑。使用者文字提及路徑不足以作為證據。

比較：把 terminal mismatch 當正常會放行不同 session；在每個 caller 補例外會重複狀態判定。集中純判定及單筆修復入口保留相容性並縮小維護範圍。

測試以既有 public CLI fake Herdr fixture 為主，另用純 predicate 邊界測試；覆蓋恢復、拒絕、status 寫入、recovery、roll-call、launch capture 及接續命令。

審查補強：缺失 session 屬未知，拒絕代報；原 session 移往其他 pane 時保留存活判定，roll-call 顯示 routing-mismatch。
