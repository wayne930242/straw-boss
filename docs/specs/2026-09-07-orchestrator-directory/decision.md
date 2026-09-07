# Orchestrator 互相辨識與互通

Alignment：同一台機器上可能同時有多個 orchestrator（handoff 開出的新 tab、使用者自己開的 window）。讓每個 orchestrator 在派工前登記自己的身分與一句話工作範圍，並能直接送出事實性 delta，訊息帶上自己的 herdr pane id 讓對方可回覆。

| Question | Answer | Basis | Status |
|---|---|---|---|
| 現況缺口 | 協調者身分只隱含在各自 dispatch instruction 的 `main_agent_*` 欄位；沒有派工的協調者完全不可見，`roll-call.py` 只能把它列為 `coordinator`／`unattributed` | scripts/roll-call.py、scripts/dispatch-task.py write | grounded |
| 登記時機 | 派工前（`dispatching-work` Task 1 解析自身可達性的同一步）；skill 也可直接叫用 | 使用者要求「派工前腳本」 | confirmed |
| 登記內容 | herdr pane id、provider session/terminal 指紋、agent kind、herdr agent 名稱、cwd，加上一句話 scope | 使用者要求「大約一句話交代完畢」 | confirmed |
| 身分鍵值 | provider session 指紋（Codex 舊記錄退回 terminal id），與 `agent_matches_identity` 同一條規則 | pane id 會被重用，dispatch_session.py 已用同一規則 | grounded |
| 存活判定 | 只用 `herdr agent list` 的指紋比對；比對不到的記錄標成 `live: false` 並保留 | roll-call.py 的既有原則：缺席不是刪除或關閉的授權 | grounded |
| 訊息內容規範 | 事實、問題、答案；沿用兩句上限與 `--ref`，不帶指示或授權 | docs/roles.md「Peer messages are factual」、CONTEXT.md | grounded |
| 記錄保留 | 目錄保留失效記錄以供閱讀，但登記時清掉「無活躍 agent 且超過 7 天」者，ledger 保留 | 不設上限的話每個曾登記的 session 都留一列，目錄很快就讀不出「現在誰在協調」 | grounded |
| 注入文字預算 | i-am-orchestrator 注入上限由 1800 提高到 1900，容納這一條新規則 | 既有 stance 已在 1799；上限本意是擋重複陳述，而非擋新規則 | grounded |
| 訊息如何帶身分 | envelope 帶 `from=<名稱>`、`pane=<發送端 herdr pane id>`、`id=<message id>`；`--to` 接受名稱或 pane id | 使用者要求對方知道自己的 herdr id | confirmed |
| 傳輸與稽核 | 重用 `validate_current_sender`／`validate_live_session`／`prompt_delivery_args`／delivery ledger | scripts/dispatch_transport.py 既有機制 | grounded |

不變更：dispatch instruction schema、worker 之間的 peer 通訊、handoff 流程、既有 skill 的職責邊界。
