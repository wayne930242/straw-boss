# Codex Jev renewal by resume

Authority: `/Users/weihung/.straw-boss/dispatch/straw-boss--codex-jev-renewal-resume.json`.
Continue the [Codex adapter](../2026-09-20-codex-jev-parity/spec.md) and
[context renewal](../2026-09-17-orchestrator-context-renewal/spec.md) contracts.

## Outcome

An opted-in Codex session continues its work from Jev-pruned history through
`codex resume` in its existing Herdr pane. The worker and user own design and
verification; the main agent receives evidence and review disposition.

| Question | Answer | Basis | Status |
|---|---|---|---|
| Integration boundary? | Swap the session at renewal through `codex resume` in the same pane. | Dispatch, Option A. | confirmed |
| Activation? | Codex, `STRAW_BOSS_JEV=1`, and a nonblank `TYPESAFE_API_KEY`. Missing activation uses ordinary renewal with no Jev output or records. | Dispatch requirements. | confirmed |
| Retention contract? | Shared criteria and policy, deterministic governing-source locks, existing Codex recency pinning, threshold and truncation. Live scores never override locks. | Dispatch and existing adapter. | confirmed |
| Gate? | Preserve the existing minimum 10% backend input-token reduction gate. The existing Codex measurement function requires explicit zero-cache usage for both histories. | `scripts/straw_boss/jev_codex.py:measurement`. | grounded |
| Failure behavior? | Gate misses and failures fall back to ordinary continuity renewal. | Dispatch requirements. | confirmed |
| Enabled Codex trigger and ordering? | Keep the existing 200,000-token Stop threshold; attempt Jev before ordinary renewal. A long turn can still reach native auto-compaction before Stop. | User approved the recommended 200k / Jev-first / ordinary-fallback option on 2026-09-21. | confirmed |
| Compatibility? | Ordinary Codex and Claude renewal stay unchanged; preserve the acceptance baseline through 2026-09-25. Activation remains session-local. | Dispatch requirements. | confirmed |
| Recovery? | Save lossless original rollout, candidate, scoring decisions, and benchmark in the private Jev store before switching. | Dispatch requirements and existing private storage boundary. | confirmed |
| Git lifecycle? | Work in the primary checkout on `main`, then commit directly. Push, version bump, and installer each require authorization in this pane. | Dispatch overrides the broader historical delivery default. | confirmed |
| Verification? | Repository pytest suite, vendor npm test/build, real same-pane enabled Codex resume with candidate-history proof, fallback exercise, and independent fresh-context review. | Dispatch reality anchor and checkpoint. | confirmed |

## Implementation investigation

The clean starting tree is `7357114`. The Stop guard currently selects the
Claude-only Jev 300k threshold through `jev_renewal.enabled`; Codex uses the
ordinary 200k threshold. `renew-context.py` writes a continuity record and starts
the detached deliverer. The deliverer waits for the turn to end, clears the
pane, then prompts continuation. SessionStart consumes the record and adopts
session routes; Stop confirms the adoption and handles over-threshold renewal
loop suppression.

`jev_codex.py` already extracts replacement history, locks pairs, applies scores,
and appends a fresh compacted record. `jev_codex_judge.py` is a regression replay
judge, with a 32k envelope check. Production scoring needs the shared 25k-state /
30k-request fitting and batching contract. The vendored `state.ts` and
`compact.ts` implement that contract and are the reuse candidates.

Production measurement and the pane transport still need prototypes. The
existing gate accepts backend usage from isolated copied resumes; estimates
used to fit Jev requests do not establish input-token savings. The transport
must validate the original pane/session, retain recovery across a failed
restart, and prove that the new process loaded the candidate. Preserve launch
configuration and role/session adoption as part of that proof.

Core rules ready: English artifacts and agent prompts, Traditional Chinese user
communication, private recovery, scoped changes, verification before success,
and contract reporting. The user has resolved the trigger decision; no consequential user-owned decision remains open.

## Sources

- `scripts/context-renewal-guard.py`
- `scripts/renew-context.py`
- `scripts/deliver-renewal.py`
- `scripts/orchestrator-priming.py`
- `scripts/straw_boss/renewal.py`
- `scripts/straw_boss/jev_codex.py`
- `scripts/straw_boss/jev_codex_judge.py`
- `scripts/straw_boss/jev_private.py`
- `vendor/fast-jev-compaction/src/state.ts`
- `vendor/fast-jev-compaction/src/compact.ts`
- Private replay evidence: `~/.straw-boss/evidence/jev-codex-parity-round3/`
