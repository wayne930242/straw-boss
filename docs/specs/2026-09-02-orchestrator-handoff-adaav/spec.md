Status: approved
Approved at: 2026-09-02T11:33:05+08:00
Approved from: user reply "確認"

# Observable contract

1. An orchestrator may propose moving an explicit work scope to a new
   orchestrator, but creates no new user-facing window until the user approves
   that one decision.
2. After approval, Straw Boss opens an independent Herdr tab, gives it a compact
   work identity, starts a new orchestrator, and tells it to route the transferred
   scope through `boss-say` before accepting the handoff.
3. The handoff contains only goal and scope, confirmed decisions and canonical
   user terms, current state and evidence, next action, and exclusions. It does
   not copy the conversation.
4. Ownership moves only after the receiving orchestrator establishes that route
   and accepts from its own recorded Herdr pane. The original
   orchestrator then performs no monitoring, routing, reporting, scheduling, or
   cleanup for that scope.
5. If the original retains separate work, both windows continue independently.
   If it retains none, it reports the completed handoff compactly and closes its
   own pane automatically.
6. Acceptance is attempted twice. If neither succeeds, the new tab is closed,
   the original keeps ownership, and it reports the failure compactly. A cleanup
   failure is reported explicitly rather than treated as a completed close.
7. Orchestrators follow ADAAV as an internal ordering: 對齊目標與使用者用語、
   延續已確認狀態、定錨現實檢查、實作、驗證。這個順序不要求階段標題、
   流程旁白、重複脈絡或每階段各自產生文件。

## Compatibility and boundaries

- `docs/roles.md` remains the authority source.
- Existing worker dispatch status, plan, watcher, and cleanup records remain
  unchanged. An orchestrator handoff is ownership transfer, not a parent-child
  dispatch and not another task in the original orchestrator's plan.
- `boss-say` remains the receiving orchestrator's route into actual work.
- User authorization and work-scope conflicts remain user decisions.
- Existing in-tab worker dispatch stays in the coordinator's tab.

## Reality anchor

Focused tests exercise generated prompts and a fake Herdr handoff: approval is a
prerequisite, the new tab is independently named, the continuity payload stays
bounded, acceptance moves ownership, failed acceptance keeps ownership and
closes the new tab, and a source with no retained work closes only after an
accepted handoff. A fresh-context review checks prompt inflation and authority
leaks.
