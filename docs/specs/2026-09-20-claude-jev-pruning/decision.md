# Claude Jev pruning with benchmark recording

Owner: the dispatched agent and the user. This is a new change alongside
[context renewal](../2026-09-17-orchestrator-context-renewal/spec.md).

## Outcome and scope

Vendor the MIT-licensed fast-jev-compaction implementation, preserve user and
assistant text verbatim, record recoverable pruning decisions, and prove a real
Claude Code compaction on this machine. Activation is explicit per session or
switch; ordinary sessions retain the renewal acceptance baseline through
2026-09-25. Codex pruning and retention-quality research are separate work.

Source authority: `/Users/weihung/.straw-boss/dispatch/straw-boss--jev-claude-side-integration.json`.
Reference: <https://github.com/tamaratran/fast-jev-compaction>.

## Decisions

| Question | Answer | Basis | Status |
|---|---|---|---|
| Source ownership? | Vendor and attribute the MIT source; build our own implementation. | Dispatch task section 1. | confirmed |
| Pruning semantics? | Lock the first and latest six messages, pair calls and results, use two noul scores with threshold 0.5, preserve text, truncate retained-call results to 300 characters plus a note. | Dispatch task section 2. | confirmed |
| Missing or empty key? | Skip silently, write no benchmark, and leave built-in behavior available. | Dispatch task section 2. | confirmed |
| Trigger mechanism? | Handle compaction events; add no percentage-based trigger. | Dispatch task section 2. | confirmed |
| Benchmark and recovery? | One JSONL record per attempted run, exact criteria version, backend token accounting, and original dropped/truncated content. | Dispatch task section 4. | confirmed |
| Initial activation? | Install and test locally, remain opt-in. | Dispatch task section 5. | confirmed |
| Current runtime? | Claude Code 2.1.278; user autoCompactWindow is 300000; function-hook flag is unset; API key is present. | Local read-only inspection on 2026-09-20. | grounded |
| Existing renewal order? | A Stop above 200k requests renewal before the 300k compaction backstop is normally reached. | Existing renewal spec and design. | grounded |
| What fires first in an opted-in session? | Let the existing 300k compaction event attempt pruning first; change renewal ordering only for explicitly enabled Claude sessions. | User selected pruning first on 2026-09-20. | confirmed |
| What is the reduction gate? | At least 10% reduction, measured using backend-reported input tokens. | User selected 10% on 2026-09-20. | confirmed |
| What follows a miss or Jev failure? | Run built-in compaction; renew at the turn boundary only if context still exceeds 300k afterwards. | User selected this fallback order on 2026-09-20. | confirmed |
| Must Codex and Claude behave consistently? | Yes. Coordinate the same activation, pruning, gate, fallback, renewal, and benchmark contract across both providers; report provider limitations as gaps. | User explicitly requested parity and notification of the coordinator on 2026-09-20. | confirmed |
| How does Round 2 change the retention criteria? | Revise the criteria and retest governing evidence retention before completing the experimental implementation; retain the 0.5 decision threshold and version the revised wording. | User selected criteria repair and retest on 2026-09-20 after reviewing the observed provenance loss. | confirmed |
| Exact activation and deactivation interface? | A session-scoped environment switch, default off; document explicit on/off launches. | Per-session opt-in is authorized; interface spelling is an implementation choice. | grounded |

## New evidence

`/tmp/jev-retention-quality.9zagAt/result.md` reports all 44 unlocked pair
judgments as drop under the original criteria, including governing contract
and instruction reads. A real copied-history continuation observed the missing
contract provenance. Savings gates do not establish retention quality.

Original criteria hash:
`sha256:f601f6f1ea411777330547aa8b075c84aad64d761f7f53dbdb608e7aa029b324`.
Revised criteria must identify their new hash and retain a regression comparison.

## Concrete scenarios

- An ordinary session follows existing renewal and emits no Jev benchmark.
- An opted-in session compacts and produces a backend-measured applied result.
- Low reduction or a failed Jev request preserves built-in compaction.
- An empty key skips Jev with no exception, notice, or benchmark.
- A mistaken deletion is recoverable from the recorded original content.

Core rules readiness: AAAAV durable workflow, repository English documentation,
MIT attribution, and dispatch reporting apply. User-owned integration decisions
remain open before production implementation.

## Delegated implementation decision: governing-source locks

The main agent relayed the user's authorization to complete implementation and
specification decisions autonomously on 2026-09-20. Five wording variants showed
that a 0.5 semantic threshold alone alternates between losing the governing
instruction read and retaining nearly everything. Preserve governing-source
reads mechanically in addition to the first/recent locks: dispatch contracts and
instruction JSON, project AGENTS/CLAUDE/GEMINI guidance, and skill instructions.
Use the separated call/result criteria (v4) for all other eligible pairs.

This extends the settled lock set to enforce the user's newly confirmed retention
requirement; it does not change 0.5 scoring, 10% savings, verbatim text, or fallback.
Its exact patterns and policy version are shared with Codex. Document the extension
as a settled-design amendment and verify both retained provenance and savings.
