# Verification

| Requirement | Evidence | Result |
|---|---|---|
| 1. One JSON line per Codex renewal, appended once at the renewed session's first Stop, deduped by `usage_recorded` | `tests/test_codex_renewal_usage.py::test_ordinary_renewal_records_usage_with_jev_disabled` runs the real `context-renewal-guard.py` hook twice for the same renewed session and asserts exactly one line in `~/.straw-boss/renewal/codex-usage.jsonl` | pass |
| 2. `path` in `{jev-applied, jev-gate-miss, jev-failure, ordinary-jev-off}` with `path_reason` | `test_ordinary_renewal_records_usage_with_jev_disabled` (`disabled`), `test_ordinary_renewal_reports_blank_key_reason` (`blank-api-key`), `test_jev_failure_schedule_failed_when_enabled_but_no_request`, and -- through the real `context-renewal-guard.py` subprocess -- `test_jev_applied_renewal_recorded_through_the_real_guard`, `test_jev_gate_miss_recorded_through_the_real_guard`, `test_jev_failure_recorded_through_the_real_guard` in `tests/test_codex_renewal_usage.py` | pass |
| 3. `post_renewal` gives input/cached input/output from the renewed session's own last `token_count` at that first Stop | `test_ordinary_renewal_records_usage_with_jev_disabled` asserts the exact triple against a fabricated transcript | pass |
| 4. `jev` block carries Jev/TypeSafe usage plus separate `probe.baseline_resume_usage`/`probe.candidate_resume_usage`, present whenever a Jev request was scheduled | `test_jev_block_keeps_probe_and_jev_tokens_separate` asserts the Jev token count and the two probe triples independently | pass |
| 5. `native-300k-compaction` line, deduped per session, only for a session that is not its own `jev_candidate_session`, with the stated limitation | `test_native_compaction_recorded_once_below_threshold`, `test_no_native_compaction_signal_without_a_compacted_row`, `test_jev_candidate_session_own_compacted_row_is_not_native_compaction` in `tests/test_codex_renewal_usage.py` | pass |
| 6. No renewal threshold, gate ratio, or path-selection change; works with `STRAW_BOSS_JEV` unset and writes nothing under `~/.straw-boss/jev/` | Every guard integration test in `tests/test_codex_renewal_usage.py` runs with `STRAW_BOSS_JEV` unset except the one `blank-api-key` case (which sets it with a blank key, the other silent-skip branch); full existing renewal/Jev suites (`tests/test_context_renewal.py`, `tests/test_jev_codex_renewal.py`, `tests/test_jev_codex.py`) pass unchanged, proving the new branches did not alter existing gating | pass |
| 7. Records hold only usage counts, identifiers, and classification strings -- no transcript or payload text | `renewal_usage.py`'s record builders (`record_renewal`, `record_native_compaction`) only read numeric usage fields and identifier strings off `continuity`/`archived`; reviewed by inspection, no transcript/payload field is copied into either record | pass |

## Distinct verification claims

- Local automated tests, before the fresh-context review: `uv run --with pytest pytest -q tests` -- 576 passed, 238 subtests passed, exit 0 (11 tests in `tests/test_codex_renewal_usage.py`, plus the full pre-existing `test_context_renewal.py` / `test_jev_codex_renewal.py` / `test_jev_codex.py` suites, unchanged).
- Local automated tests, after the review-driven fixes: `uv run --with pytest pytest -q tests/test_codex_renewal_usage.py` -- 14 passed (3 new subprocess-integration tests for `jev-applied`/`jev-gate-miss`/`jev-failure` added); `uv run --with pytest pytest -q tests/test_context_renewal.py tests/test_jev_codex_renewal.py tests/test_jev_codex.py` -- 85 passed (confirms the `codex_transcript_summary` consolidation is behavior-preserving); full `uv run --with pytest pytest -q tests` -- 579 passed, 238 subtests passed, exit 0 (up from 576 for the 3 added tests; no regressions).
- No build/compilation step applies (pure Python, no `npm test`/`npm run build` target touched by this change).
- No interactive/CLI, browser, or deployment verification was run; this is a background hook change with no UI surface, matching the task's "Recording only" scope.

## Human appropriateness

Not applicable -- no UI or human-use scenario; the deliverable is a private, machine-readable log for later human/agent comparison, not an interactive surface.

## Deviations

None from the approved spec.md/design.md.

## Unresolved gaps

- The native-300k-compaction detector has not been observed against a real Codex session that actually crossed 300k in production; its correctness rests on the transcript-shape analysis in decision.md/design.md and the fabricated-row unit tests above, not a live occurrence.
- `classify()`'s `disabled` vs. `blank-api-key` vs. `schedule-failed` split for the Jev-off/failure buckets is inferred from the *current* environment at record time rather than the *original* session's environment at renewal time (see design.md's trade-offs); not separately reproduced against a live pane where the two could diverge.

## Reflexive pass

A fresh-context review agent audited the diff against `design.md`/`spec.md`
before this pass and raised two items, both recorded as friction notes in
`design.md`'s `## Friction Notes` and fixed:

- Gap: `design.md`'s own coverage list promised subprocess-integration tests
  for all four paths, but the first pass only wired up
  `ordinary-jev-off`/native-300k through the real guard; the three
  Jev-attempted paths were unit-tested only. Closed by adding
  `_jev_fixture()` and three subprocess tests.
- Gap: no instruction anticipated that the two new Stop-hook blocks could
  both fire in the same Stop and each independently re-parse the
  transcript. Closed by consolidating into the single
  `codex_transcript_summary()` call described in `design.md`'s Interfaces
  section, with `record_renewal`/`record_native_compaction` now taking the
  already-parsed values.

Both fixes are covered by the evidence rows above and the full suite run
recorded under Distinct verification claims.
