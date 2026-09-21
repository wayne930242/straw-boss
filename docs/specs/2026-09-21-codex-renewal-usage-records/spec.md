Status: approved
Approved at: 2026-09-21
Approved from: User approved the spec as written and chose to include the native-300k-compaction detector (item 5) in this round, via AskUserQuestion in this dispatched session.

# Observable contract

Implement the requirements and scope in [decision.md](decision.md).

1. Every Codex context renewal that goes through
   `renew-context.py` / `deliver-renewal.py` writes exactly one JSON line to
   `~/.straw-boss/renewal/codex-usage.jsonl`, appended once at the renewed
   session's first Stop
   ([context-renewal-guard.py](../../../scripts/context-renewal-guard.py)),
   gated by a new `usage_recorded` flag on the continuity record so a later
   Stop in the same renewed session never re-appends.
2. Each renewal line names `path` as one of `jev-applied`, `jev-gate-miss`,
   `jev-failure`, `ordinary-jev-off`, plus a `path_reason` (the Jev
   `fallback_reason`, `schedule-failed`, `disabled`, or `blank-api-key`).
3. Each renewal line's `post_renewal` block gives `input_tokens`,
   `cached_input_tokens`, and `output_tokens` from the renewed session's own
   last `token_count` event at that first Stop -- the same measurement for
   every path.
4. Whenever a Jev request was scheduled (`jev-applied`, `jev-gate-miss`,
   `jev-failure`), the line's `jev` block carries the Jev/TypeSafe
   `input_tokens`/`requests`/`latency_ms`/`model` already computed by
   `deliver()`, plus `probe.baseline_resume_usage` /
   `probe.candidate_resume_usage` (input/cached input/output), each kept
   separate from `post_renewal` so the two billing sources
   (TypeSafe vs. ChatGPT-plan Codex quota) stay summable independently.
5. A session whose own rollout carries a `compacted` row that is not its
   confirmed `jev_candidate_session`, observed while its Stop-time tokens
   are at or below the 200k threshold, appends one
   `native-300k-compaction` line (deduplicated per session) with the
   post-compaction usage triple and a stated limitation: only the
   post-compaction snapshot is captured, not the pre-compaction peak, and a
   compaction that does not end up at or below the threshold is not
   tracked.
6. No renewal threshold, gate ratio, or path selection changes. The new
   write path runs with `STRAW_BOSS_JEV` unset and writes nothing under
   `~/.straw-boss/jev/`.
7. Records hold usage counts, session/pane identifiers, and classification
   strings only -- no transcript content, no continuity payload text.

## Non-goals

- Claude or agy renewal instrumentation.
- Any dashboard, aggregation, or comparison tooling over the new log --
  this ships the record only.
- Distinguishing a second native compaction inside an already-Jev-resumed
  session from the first (see limitation in item 5).

## Standards and reality anchor

Apply `AGENTS.md`'s English-source rule and the repository's existing
Codex-renewal test conventions
(`tests/test_context_renewal.py`, `tests/test_jev_codex_renewal.py`).
Reality anchor: testing.
Add failing-first coverage for `renewal_usage.py`'s classification and
the guard's new Stop-hook branches, then `uv run --with pytest pytest -q
tests`.
Checkpoint: one fresh-context review of the finished change-set before
shipping.

