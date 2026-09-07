# 驗證

Reality anchor：testing。公開 CLI 在假 herdr fixture 下的真實行為（`tests/test_orchestrator_directory.py`，14 項），加上在本機真實 herdr 上跑同一組 CLI。

| Requirement | Evidence | Result |
|---|---|---|
| 1 登記寫入記錄並回傳目錄 | `test_registering_records_this_session_and_returns_the_live_directory`；真實 herdr 執行 `register-orchestrator.py --scope`，寫出 `~/.straw-boss/orchestrators/claude-e8568e43-….json`，`live: true` | pass |
| 2 重新登記更新同一筆 | `test_re_registering_updates_the_same_record`（單一檔案、scope 更新、`registered_at` 保留） | pass |
| 3 缺 pane／pane 無活躍 agent／不支援的 agent kind 拒絕 | `test_registering_needs_a_live_agent_in_this_pane`、`test_an_agent_kind_with_no_delivery_path_is_refused` | pass |
| 4 scope 非空、單行、≤200 字元 | `test_a_scope_is_one_short_line` | pass |
| 5 `--list` 標記存活與失效並保留檔案 | `test_a_record_whose_session_ended_lists_as_not_live_and_is_kept`；真實 herdr `--list` 輸出目前 pane 與 `live: true` | pass |
| 5a 登記時淘汰逾 7 天的失效記錄、ledger 保留 | `test_registering_retires_records_whose_session_ended_a_week_ago`、`test_a_week_old_record_whose_session_is_still_live_is_kept` | pass |
| 6 envelope 帶 intent、id、名稱與發送端 pane id | `test_a_delta_reaches_the_other_orchestrator_naming_this_pane`（斷言 `[orchestrator inform `、`id=`、`from=`、`pane=wA:p1`、`refs=[…]`） | pass |
| 7 發送端須已登記且 pane 與 live session 相符 | `test_an_unregistered_orchestrator_is_refused`；每個成功送出案例都經過 `validate_current_sender` | pass |
| 8 收件端身分不符拒絕、無活躍 agent 記為未送達 | `test_a_target_pane_holding_another_session_is_refused`、`test_a_target_whose_session_ended_is_recorded_undelivered`；真實 herdr 上未登記目標回 `no registered orchestrator matches 'w3:p1'` | pass |
| 9 answer 必須對應收到過的 question | `test_an_answer_names_the_question_it_replies_to`（偽造 id 被拒、真實 id 通過） | pass |
| 10 兩句上限與 ledger 記錄 | `test_a_message_body_stays_a_delta`、同組測試對 `claude-orchestrator-b.messages.jsonl` 的斷言 | pass |
| 11 skill 與兩處入口 | `skills/contacting-orchestrators/SKILL.md`；`dispatching-work` Task 1 與其驗證條款；`i-am-orchestrator` 注入文字；`tests/test_skill_instruction_quality.py`（58 項）與注入預算測試通過 | pass |

全套 `python -m unittest`：315 項通過（新增前 313 項）。

# 偏離與缺口

- 注入文字預算由 1800 提高到 1900：既有 stance 已佔 1799，新規則佔 96 字元。防重複陳述的斷言未改動，仍是實際守門。決策記在 `decision.md`。
- 兩個真實 orchestrator pane 之間的實際投遞未實測：那會把 prompt 送進使用者另一個活著的 session，未經同意不做。投遞本身走的是既有派工訊息相同的 `herdr agent prompt` 接縫，CLI 邊界由假 herdr 測試覆蓋。
- 未做 commit／push；本次僅本機驗證。
