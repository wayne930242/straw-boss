# Decision

## Outcome and actors

The user (a Straw Boss main agent, via this dispatch) needs to compare, after
2026-09-25, a Jev-applied Codex context renewal against an ordinary Codex
continuity renewal on real work.
Today only the Jev-attempted path leaves any record
([jev_codex_renewal.py](../../../scripts/straw_boss/jev_codex_renewal.py)'s
`save()` writes to `~/.straw-boss/jev/benchmark.jsonl`, but only when
`schedule()` in
[renew-context.py](../../../scripts/renew-context.py) actually scheduled a
Jev request).
This work adds one comparable, machine-readable record per Codex context
renewal, independent of whether Jev ran.

## In scope

- A new append-only log under `~/.straw-boss/`, written once per Codex
  renewal, classifying which path ran and giving post-renewal Codex usage
  (input, cached input, output) for that path.
- Reusing the renewed session's first Stop (`consumed_by == session`) as the
  measurement window for both paths, since that is the point
  [jev_codex_renewal.py](../../../scripts/straw_boss/jev_codex_renewal.py)'s
  `observe()` already uses for the Jev path, and it is exactly "the first
  turn, plus the re-reading it spends before getting back on task" for
  either path (a Codex turn's `last_token_usage` already accumulates every
  tool call inside that turn).
- A best-effort detector for Codex's native 300k compaction preempting the
  200k Stop, using the fact that our system never writes a `compacted` row
  into a session's own rollout file except through
  `jev_codex_transport.register_rollout` on the resumed candidate session
  (verified against `~/.codex/archived_sessions/*.jsonl`).

## Out of scope

- Any change to renewal thresholds, gate ratios, or which path is attempted.
- Claude or agy renewal (task constraint: Codex only).
- Enabling Jev globally; the new record must be written with
  `STRAW_BOSS_JEV` unset.

## Concrete scenarios

1. Jev applies: renewed session resumes into the candidate session; record
   captures `jev-applied`, the Jev/TypeSafe probe usage already computed by
   `deliver()`, and the candidate session's first-Stop Codex usage.
2. Jev schedules but the gate rejects the candidate
   (`fallback_reason` `unchanged-candidate` or `under-reduction-gate`):
   record captures `jev-gate-miss` plus the ordinary-renewed session's
   first-Stop usage.
3. Jev schedules but preparation or resume raises
   (`fallback_reason` `preparation-*` / `resume-*`), or `schedule()` itself
   raised in `renew-context.py`: record captures `jev-failure`.
4. `STRAW_BOSS_JEV` unset, or `TYPESAFE_API_KEY` blank: record captures
   `ordinary-jev-off`.
5. A Codex turn crosses 300k and gets natively compacted before our 200k
   Stop ever sees the growth (so no renewal record above is produced at
   all): a separate `native-300k-compaction` record captures the
   post-compaction usage snapshot, once per session.

## Confirmed decisions

| Question | Answer | Basis | Status |
|---|---|---|---|
| Where does the new record live? | `~/.straw-boss/renewal/codex-usage.jsonl`, append-only, one JSON line per renewal event, flock-protected | Sits beside the existing per-pane continuity records in `renewal_root()`; independent of `~/.straw-boss/jev/`, so it works with Jev off | grounded |
| What is the post-renewal measurement window? | The renewed session's first Stop (`record.consumed_by == session`) | Same point `observe()` already uses for the Jev path; keeps both paths measured identically per the task's acceptance criterion | grounded |
| How is the path classified? | `jev-applied` / `jev-gate-miss` / `jev-failure` / `ordinary-jev-off`, derived from the Jev per-run archive's `decision`/`fallback_reason` when `jev_request` was scheduled, else from `jev_renewal.enabled()` at record time | Matches existing `jev_codex_renewal.deliver()` semantics; `schedule()` failure (caught silently in `renew-context.py`) is classified `jev-failure` reason `schedule-failed` since Jev was active but never got to run | grounded |
| Is native 300k compaction observable? | Yes, best-effort: a `compacted` row in a session's own transcript that is not that session's confirmed `jev_candidate_session` is unambiguous native compaction | Verified against live rollout samples; our code never writes that row type into an original session's own file | confirmed -- see spec.md open item |
| Concurrency safety | flock-protected append, mirroring `jev_storage.benchmark_lock()` | Multiple panes can renew concurrently | grounded |
| Reality anchor | Testing: `tests/test_context_renewal.py` and `tests/test_jev_codex_renewal.py`, plus `uv run --with pytest pytest -q tests` | Dispatch names anchor "testing" and the app's own verification command | grounded |

Core rules ready: English source, tests, and skill artifacts per
[AGENTS.md](../../../AGENTS.md); Traditional Chinese user communication; the
new log follows `renewal.py`'s existing plain-file storage under
`renewal_root()` (flock-protected, not `jev_private`'s descriptor-relative
store, since it must work with Jev off) while reading the Jev archive
through `jev_private` exactly as `observe()` already does; recording-only
scope (no renewal-decision or threshold changes); commit messages with no
AI-tool mention or trailer, following the repo's `type: summary` convention.
One user-owned item remains open -- see spec.md's native-300k-compaction
scope choice -- before the first production edit.
