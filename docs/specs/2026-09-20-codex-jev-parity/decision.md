# Codex Jev parity

Authority: `/Users/weihung/.straw-boss/dispatch/straw-boss--jev-codex-parity.json`.
Carry the confirmed [shared decisions](../2026-09-20-claude-jev-pruning/decision.md) and canonical config unchanged.

| Question | Answer | Basis | Status |
|---|---|---|---|
| Activation and delivery? | Opt-in; implement and ship, then review benchmark evidence. | Dispatch round 3 and user authorization. | confirmed |
| Scores and locks? | v4 criteria, current shared policy (v3 at final replay), 0.5 threshold, governing-source locks. | Canonical hashes verified locally. | confirmed |
| Gate and fallback? | Backend zero-cache input reduction >=10%; otherwise built-in compaction, then renewal only above the window. | Confirmed shared contract. | confirmed |
| Provider limitations? | Report unsupported history-replacement integration as a gap; exercise copied resumable histories. | Dispatch explicitly requires copies and gap reporting. | confirmed |

Core rules ready: English artifacts, scoped edits, copied evidence, source hash checks, and dispatch status reporting. No open user-owned decision.
