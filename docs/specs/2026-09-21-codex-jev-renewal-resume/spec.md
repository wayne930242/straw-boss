Status: approved
Approved at: 2026-09-21
Approved from: The dispatch authorizes implementation of Option A; the user approved the recommended 200k threshold, Jev first, and ordinary renewal on failure in this pane.

# Observable contract

Implement the requirements and scope in [decision.md](decision.md).

1. Activate only for Codex with `STRAW_BOSS_JEV=1` and a nonblank key. Disabled sessions use ordinary renewal with no Jev output or records.
2. At Stop above 200,000 input tokens, attempt Jev before ordinary renewal. Preserve the existing turn and renewed-session loop guards.
3. Score the live, completed rollout with shared criteria/policy, deterministic locks, Codex recency pinning, the keep threshold, truncation, and production 25k-state/30k-request fitting.
4. Append a fresh compacted replacement record to a candidate copy. Preserve user/assistant/reasoning items and complete call/result relationships.
5. Apply the existing minimum 10% backend input-token reduction gate with explicit zero-cache measurements. Inconclusive measurement falls back.
6. Persist lossless recovery and benchmark evidence in the private Jev store before application. Distinguish candidate measurement, gate selection, and observed live application.
7. Resume the candidate through `codex resume` in the same Herdr pane, retaining launch configuration, role, and session routing. Ordinary continuity renewal handles gate misses and failures.
8. Preserve ordinary Codex and Claude behavior, the baseline through 2026-09-25, and session-local activation. Keep shell startup and global configuration unchanged.
9. Complete the authorized solo-mode local commit on main. Push, version bump, and installation each need explicit authorization in this pane.

## Standards and reality anchor

Apply AGENTS.md language and verification rules and the existing descriptor-based private-store boundary. Run `uv run --with pytest pytest -q tests`, vendor `npm test` and `npm run build`, and real Herdr/Codex enabled and fallback probes. Show that the same pane resumes the exact candidate history. Obtain an independent fresh-context review of the finished change-set before wrap-up. Record results per requirement in verification.md.
