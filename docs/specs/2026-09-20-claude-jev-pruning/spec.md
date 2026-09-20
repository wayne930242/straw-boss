Status: approved
Approved at: 2026-09-20
Approved from: User confirmed, "Confirmed; implement and verify accordingly."

# Opt-in Claude Jev compaction

Decisions: [decision.md](decision.md).

## Observable contract

1. Vendor the MIT reference implementation at upstream commit
   `e3f262a7f4d42bd8dd32ced30d26176f7cb545b0`, retaining attribution and license.
   Install our implementation locally for deliberate session use.
2. Default activation is off. A documented session switch enables Claude
   pruning and its renewal integration; disabling it restores existing behavior.
   An unset or empty `TYPESAFE_API_KEY` silently skips the entire Jev path,
   including benchmark writes and changes to renewal ordering.
3. Handle existing compaction events, with no independent percentage trigger.
   In enabled Claude sessions, let compaction at the configured 300k window
   attempt Jev before renewal. Other sessions retain the existing 200k renewal.
4. Preserve governing-source reads identified by the shared policy (dispatch
   contracts/instruction JSON and AGENTS/CLAUDE/GEMINI/SKILL guidance), plus
   the first and latest six messages and both sides of each locked
   pair. Preserve all user and assistant text verbatim. Fit the judging view
   near 25k tokens using staged shrinking and result-body stand-ins; keep
   requests within the Jev context constraints.
5. Ask two noul questions per unlocked pair. At 0.5, keepResult retains both;
   keepCall alone retains the call and at most the first 300 result characters
   plus an omission note; neither retains the pair. Unpaired calls are retained.
6. Revise the original criteria to preserve currently governing instructions,
   mandatory contract provenance, and evidence required for unfinished work.
   Store exact wording centrally with a stable hash. Retest against the durable
   Round 2 baseline and report retained/truncated/dropped distributions and
   qualitative evidence. Share the wording, hash, and evidence with the main
   agent for Codex parity.
7. Apply a candidate only when backend input-token measurements establish at
   least 10% reduction. Record measurement provenance and scope; distinguish
   candidate counts, actual post-compaction usage, and fallback usage. A local
   serialized-JSON token estimate does not satisfy the gate or benchmark.
   Missing measurement capability is a recorded fallback and a delivery gap
   until the real application path is demonstrated.
8. A gate miss or Jev failure uses Claude built-in compaction. Afterwards,
   renewal runs at a turn boundary only if current context still exceeds 300k.
   Applied pruning likewise renews if the resulting context remains above
   300k. A fallback followed by a sufficiently small context does not renew.
9. Each attempted run records JSONL containing trigger, tokens_before,
   context_window, jev.model from responses, jev.requests, jev.input_tokens,
   jev.latency_ms, criteria_version, decisions with call_id/tool/keepCall/
   keepResult/action/bytes_before/bytes_after, tokens_after, reduction_pct,
   decision, outcome, application verification state, and fallback_reason.
    `outcome: applied` requires a subsequent backend usage observation; before
    that it is null with an explicit pending application state. Unknown values are explicit. Include per-request
   metrics and distinguish total request latency from elapsed wall time.
10. Persist complete original modified content and positions before applying
    pruning. Recovery reconstructs the original tool records. Storage remains
    local with user-only access. A persistence failure uses built-in compaction.
11. On/off instructions identify session restart requirements and the benchmark
    location. Ordinary compactions stay outside the experiment so the renewal
    acceptance baseline through 2026-09-25 remains interpretable.

## Compatibility and scope

Codex and Claude share the user-visible contract. The main agent routes Codex
implementation separately; Claude-only evidence does not prove Codex parity.
The existing renewal spec remains the historical baseline. This change adds
opt-in behavior alongside it and preserves dispatch identity and renewal-record
contracts. No upstream plugin installation or default-on pruning is included.

## Applied standards

- Repository English prose and tests; Traditional Chinese user communication.
- AAAAV durable artifacts and verification claims separated by evidence type.
- Existing renewal ownership, role priming, and dispatch identity rules.
- MIT attribution and pinned upstream provenance.

## Reality anchor and checkpoint

- Local tests cover preservation, pairing, threshold decisions, recovery,
  missing-key silence, fallback, benchmark accounting, and renewal integration.
- Real Jev requests on the durable Round 2 cases demonstrate revised retention
  decisions; a continuation check exercises the formerly missing provenance.
- A real Claude Code 2.1.278 compaction produces a recoverable benchmark record
  and proves the applied and fallback paths using backend token measurements.
- Local installation is inspected with activation off; on/off commands are
  exercised. The repository suite runs with `uv run --with pytest pytest -q tests`.

Checkpoint: production edits follow user confirmation; completion requires the
real Claude compaction record and a separate standards/spec diff review. Record
remaining provider or parity gaps as unknown rather than complete.
