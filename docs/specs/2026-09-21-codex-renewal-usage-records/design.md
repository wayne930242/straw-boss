# Design

## Approach

New module `scripts/straw_boss/renewal_usage.py` owns the log and its
classification.
Two call sites in `scripts/context-renewal-guard.py` invoke it; no other
file changes behavior.

```
context-renewal-guard.py (Stop)
  |
  |-- record.consumed_by == session, not usage_recorded
  |     -> renewal_usage.record_renewal(record, session, transcript)
  |          -> classify(record, session)    [reads jev archive via jev_private, if jev_request]
  |          -> renewal.codex_last_token_usage(transcript)
  |          -> append(entry)                [flock-protected, renewal_root()]
  |
  |-- tokens <= threshold, agent_kind == codex, session is not the jev candidate
        -> renewal_usage.record_native_compaction(session, pane_id, transcript)
             -> renewal.codex_has_compacted_row(transcript)
             -> dedupe marker under renewal_root()/native-compaction-seen/
             -> append(entry)
```

## Interfaces and data flow

`renewal.py` gains two small, behavior-preserving reads over the same
already-parsed transcript list (`_jsonl_reversed`), reused by both the
existing `codex_context_tokens` and the new code:

- `codex_last_token_usage(transcript) -> dict | None`: the full
  `last_token_usage` dict (input/cached input/cache write/output/reasoning
  output/total) of the last `token_count` event.
  `codex_context_tokens` becomes a one-line wrapper over it -- no behavior
  change, covered by the existing
  `test_codex_measure_reads_the_last_token_count`.
- `codex_has_compacted_row(transcript) -> bool`: any row with
  `type == "compacted"` in that transcript.
  Verified against a live rollout
  (`~/.codex/archived_sessions/*.jsonl`) that native auto-compact and our
  own `jev_codex.replacement_rows` both use this row type, and that our
  code only ever writes it into the *candidate* session's own file via
  `jev_codex_transport.register_rollout`, never into an original session's
  file.

`renewal_usage.py`:

- `usage_path() -> Path`: `renewal.renewal_root() / "codex-usage.jsonl"`.
- `append(entry: dict) -> None`: flock on a sibling `.lock` file
  (mirrors `jev_storage.benchmark_lock()`), single `O_APPEND` write,
  `flush()` + `fsync()`. Each renewal or native-compaction event is
  computed once, fully, before this call -- no read-modify-write, unlike
  `jev_codex_renewal.save()`'s upsert (which exists because a Jev record is
  written twice over time; here each Stop writes at most one line for
  itself).
- `classify(continuity: dict, session: str) -> tuple[str, str | None, dict | None]`:
  - no `continuity["jev_request"]`: `jev_renewal.enabled("codex", ...)`
    decides `ordinary-jev-off` (`disabled` / `blank-api-key`) vs.
    `jev-failure` (`schedule-failed`) -- the latter covers
    `renew-context.py`'s silent
    `except (ValueError, OSError, KeyError): pass` around `schedule()`.
  - `jev_request` present: read the request
    (`jev_private.private_read`) for `run_id`, then the archived per-run
    record at `jev_private.root() / "runs" / f"{run_id}.json"` -- the same
    two reads `observe()` already performs, so by the time any renewed
    session exists this archive is guaranteed fully written (`deliver()`
    always calls `save()` before returning or before the pane clears).
    `decision == "apply"` -> `jev-applied`.
    `fallback_reason` in `{"unchanged-candidate", "under-reduction-gate"}`
    -> `jev-gate-miss`.
    Anything else -> `jev-failure`.
- `record_renewal(continuity, session, transcript) -> None`: builds the
  `renewal` entry (schema below) and appends it. A `None`
  `codex_last_token_usage` result (transcript unreadable) is a silent no-op,
  matching the guard's existing `if tokens is None: return 0` posture for
  measurement gaps.
- `record_native_compaction(session, pane_id, transcript) -> None`: checks
  the per-session marker, then `codex_has_compacted_row`, then appends and
  touches the marker.

## Record schema

```json
{"schema_version": 1, "kind": "renewal", "recorded_at": "...",
 "path": "jev-applied", "path_reason": null,
 "pane_id": "...", "role": "...",
 "old_session_id": "...", "new_session_id": "...",
 "jev": {"run_id": "...", "model": ["gpt-6-astra"], "requests": 4,
         "input_tokens": 512, "latency_ms": 900, "gate_reduction_pct": 41.2,
         "probe": {"baseline_resume_usage": {"input_tokens": 200001,
                     "cached_input_tokens": 0, "output_tokens": 4},
                   "candidate_resume_usage": {"input_tokens": 118000,
                     "cached_input_tokens": 0, "output_tokens": 4}}},
 "post_renewal": {"window": "first-stop-of-renewed-session",
                   "input_tokens": 118400, "cached_input_tokens": 0,
                   "output_tokens": 812}}
```

`jev` is `null` for `ordinary-jev-off`; `jev.probe` fields are `null` when
the archived record has no measurement (e.g. a `preparation-*` failure
before `probe.measure` ran, or the `unchanged-candidate` short-circuit that
skips probing).

```json
{"schema_version": 1, "kind": "native-300k-compaction", "recorded_at": "...",
 "session_id": "...", "pane_id": "...",
 "post_compaction": {"input_tokens": 42000, "cached_input_tokens": 0,
                      "output_tokens": 900},
 "limitation": "post-compaction snapshot only; the pre-compaction peak that crossed 300k is not captured"}
```

## Precedent

- `jev_storage.benchmark_lock()` / `jev_codex_renewal.observe()`: the
  flock-append pattern and the "read the archive by run_id" pattern this
  design reuses.
- `context-renewal-guard.py`'s existing `settled` / `reported_over_threshold`
  / `confirmed` per-record dedupe flags: precedent for `usage_recorded`.
- `already_blocked_this_turn`'s per-session marker file under
  `renewal_root()`: precedent for the native-compaction dedupe marker.

## Trade-offs and risks

- `classify()` trusts `jev_renewal.enabled()`'s *current* environment to
  infer why `jev_request` is absent; if `STRAW_BOSS_JEV`/`TYPESAFE_API_KEY`
  changed between the original and the renewed session in the same pane
  (not expected in practice -- same shell), the `disabled`/`blank-api-key`
  vs. `schedule-failed` split could mislabel. `path` itself
  (`ordinary-jev-off` vs. `jev-failure`) is unaffected by this risk since
  both are already distinct buckets; only `path_reason`'s exact wording is
  approximate here.
- The native-300k detector only fires when Stop-time tokens end up at or
  below the 200k threshold (the "preempted our Stop" scenario named in the
  task); a native compaction that still leaves tokens above 200k is not
  tracked, since that case does not change which of our four paths runs.
- Both new Stop-hook branches wrap their calls in
  `except (OSError, ValueError, KeyError, json.JSONDecodeError)`, matching
  the file's existing failure posture (`observe()`'s own wrapping): a
  recording failure never blocks a turn or changes renewal behavior.

## Method inside the reality anchor

Add failing-first unit coverage for `renewal_usage.classify()` and
`append()`, then integration coverage through the real
`context-renewal-guard.py` subprocess (as `test_context_renewal.py` and
`test_jev_codex_renewal.py` already do), covering: Jev off (no jsonl
line), Jev applied, Jev gate-miss, Jev failure, and native-300k detection
plus its dedupe.
Run `uv run --with pytest pytest -q tests`.
