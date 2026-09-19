# Codex dispatch sender ownership

The worker owns its dispatch status and outgoing messages. The main agent owns cancellation and routing. This change covers Codex launch instructions and the shared sender validation seam.

| Question | Answer | Basis | Status |
|---|---|---|---|
| Which outcome is authorized? | Reject background memory writes while preserving the real worker's reports. | Dispatched task n7, `straw-boss--codex-memory-status-n7.json` | confirmed |
| Can the persisted session id distinguish the incident? | No; the incident instruction and message ledger have null ids. | n2 evidence in `~/.straw-boss/plans/schedule-qa-0919b/artifacts/` | grounded |
| What identifies the caller? | Codex supplies `CODEX_THREAD_ID` to each thread's shell; Herdr now exposes the pane's live `agent_session`. | Local Codex 0.155.1 and live n7 pane inspection; upstream shell environment implementation | grounded |
| Where does the contract leak? | The launcher supplies it through `developer_instructions`; consolidation clones that config without clearing the field. | Launch implementation and upstream memory phase 2 implementation | grounded |
| How should live older dispatches behave? | Validate the caller against the live thread even when the persisted id is null; refuse unverifiable callers before mutation. | Existing version-neutral launcher and task n7 scope | grounded |
| Is changing global memory configuration necessary? | No; scope the contract to the opening task prompt and validate sender identity. | Narrowest existing seams | grounded |

Core rules are ready: English source documentation, scoped changes on clean main, red regression, complete pytest suite, independent review, version bump, commit, push and install as authorized by the dispatch. No consequential user-owned decisions remain open.
