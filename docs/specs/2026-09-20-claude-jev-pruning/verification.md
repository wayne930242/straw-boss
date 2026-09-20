# Verification: Claude Jev pruning

Contract: [spec.md](spec.md). Operation: [../../jev-pruning.md](../../jev-pruning.md).

## Evidence disposition

The user directed shipment on 2026-09-20 with activation off and subsequent
behavior review through benchmark records. Additional live branch coverage is
explicitly deferred. The main agent commissioned a fresh-context review without blocking the opt-in
release. That review requested changes for indirect governing paths (P1) and
identified existing storage permissions/link handling (P2). The 0.30.17 follow-up
fixes dispatch-directory matching, states the remaining recognition limits, and
hardens storage access. Self-review covered standards and the amended contract;
independent re-review of the follow-up remains with the coordinator.

Durable machine-local evidence:
`~/.straw-boss/evidence/jev-claude-integration/`.
The Round 2 baseline remains at
`~/.straw-boss/evidence/jev-retention-quality-round2/`.

## Requirement evidence

| Requirement | Evidence | Result |
|---|---|---|
| 1 Vendored implementation and attribution | Pinned `vendor/fast-jev-compaction/UPSTREAM.md`, MIT license, source and upstream tests; our hook registered independently | pass |
| 2 Default off and silent missing key | Real hook loads under 2.1.278; focused tests prove disabled/missing/empty/whitespace keys delegate without benchmark writes or output, and normal renewal remains active | pass at automated boundary; missing-key live compaction deferred |
| 3 Existing compaction trigger and opt-in renewal ordering | Real `/compact` invokes `session.compact`; no proactive percentage trigger; guard requires matching loaded-session readiness, enabled switch, and key | pass for hook and focused tests; live threshold crossing deferred |
| 4 Locks, pairing and verbatim text | Upstream and adapter tests, governing-source fixture, exact original/candidate recovery views, real fixture continuation retains count and invariant | pass for exercised forms; multimodal view fidelity remains limited by provider interface |
| 5 Keep/truncate/drop policy | 0.5 threshold tests; real Jev raw v4 judgments and effective locked decisions; at least one unlocked real truncate survives protection | pass for test and fixed-history decisions; live truncate deferred |
| 6 Revised retention and parity artifacts | `criteria.json` matches config; hash `sha256:0717ecfc2a1cd44198a52958c4538c78a3e0b7d9d4338af4e47e217ac5663ebe`; effective decisions retain all recognized governing reads; main agent received shared criteria and policy | pass for shared contract and regression; Codex runtime implementation belongs to its next dispatch |
| 7 Backend 10% gate and distinct actual usage | Anthropic count_tokens on native blocks; full session input as conservative denominator; schema v2 pending decision becomes applied only after real next-request usage | pass |
| 8 Built-in fallback and renewal | Fake-engine gate/failure/storage-error tests delegate original event; renewal tests distinguish 200k ordinary and 300k opt-in, and ignore pre-compaction usage | pass at automated boundary; live fallback deferred |
| 9 Benchmark metrics and outcomes | `benchmark-final.jsonl`; real response model/usage, per-request timings, criteria/policy hashes, decision/application split, scalar and per-pair fields | pass; development schema v1 rows explicitly marked unverified |
| 10 Recoverable original content and private storage | Exact original message/pair equality and byte tests; review-follow-up tests enforce existing 0700/0600 modes and reject symlink/hardlink/FIFO/foreign-owned paths | pass at focused automated boundary |
| 11 Documentation and opt-in installation | README and operation guide contain explicit launch on/off; release installation/readback is recorded in dispatch evidence after commit | documentation pass; installation result carried by final dispatch report |

## Actual Claude runtime

Claude Code: **2.1.278**. Model: **claude-sonnet-5**, low effort.
The fixtures are synthetic completed diagnostic archives; their measurements
demonstrate mechanics, not representative task savings.

The first hook candidate selected seven old pairs for removal. Its native-history
backend count was 53,444 to 16,132, but restarting the CLI sent **55,980** actual
input tokens. Upstream unchanged-message handle reuse reconnected removed
ancestors through their old parent chain. This invalidated the initial application
claim and is preserved in `claude-live/resume.json`.

Fresh identities preserve the returned message text/tool content while creating
a new persisted chain. The subsequent real restart sent **1,795** input tokens
and answered both the ten-archive count and `KEEP_BLUE_731` correctly. Both
observations had zero cache reads. These are the persistence regression artifacts
`claude-live/compact-fresh.json` and `claude-live/resume-fresh.json`.

A separate run using schema v2 confirmed the automatic pending-record lifecycle
across restart: run
`f439832f-8490-4822-817f-52b6b35c04dc-1789904676620-5zi9cu`
records live input **56,633** before and **27,545** afterwards, `decision: apply`,
`outcome: applied`, and `application.status: verified`. The next request included
different prompt overhead, so this is a net usage observation, not an isolated
tokenizer-equivalence claim.

## Fixed real-task gate regression

`effective-decisions.json` applies v4 scores plus the shared deterministic locks.
`regression-measurements.json` counts equal native Claude projections of the
fixed Codex source with the real Anthropic backend. These are candidate-history
counts, not actual Codex resume usage or full Claude request usage.

| Checkpoint | Keep / truncate / drop | Governing locks | Backend before / candidate after | Candidate reduction | Gate |
|---|---|---:|---:|---:|---|
| table-early | 2 / 0 / 0 | 2 | 100829 / 100829 | 0% | fallback |
| table-middle | 5 / 0 / 7 | 5 | 173287 / 129904 | 25.04% | pass |
| table-late | 7 / 1 / 19 | 7 | 186422 / 117150 | 37.16% | pass |
| release-middle | 3 / 0 / 0 | 3 | 290424 / 290424 | 0% | fallback |

Raw criteria variants v2, v3, v5 and v6 are explicitly superseded. The unversioned
`criteria.json` now matches the adopted v4; `retest.json` is an artifact manifest,
not an ambiguous latest tuning output. Protected-source locks are load-bearing:
wording alone still dropped the active instruction JSON in the late checkpoint.

## Local checks

- Full repository suite: **466 passed, 199 subtests passed** (259.80 seconds).
- Subsequent affected Python/instruction suite: **66 passed, 147 subtests passed**.
- Final byte-accounting and persistence unit file: **7 passed**.
- TypeScript suites: **35 passed**; strict hook typecheck and library build pass.
- Claude plugin manifest validation and `git diff --check` pass.
- No CI or remote deployment result is inferred from these local checks.

## Amendments and limits

- Governing-source locks extend the originally specified first/recent locks to
  satisfy the confirmed retention requirement after repeated wording-only failures.
- Fresh identities fix the upstream persistence defect found by live verification.
- `outcome` may remain null until backend usage verifies an application; the
  earlier two-value schema conflated selection with actual application.
- Per-pair byte accounting counts visible content once. Development records
  originally counted duplicated host objects (49,189 bytes for each equal-length
  archive pair). They were recomputed from saved originals; the untouched old
  rows remain in `benchmark-before-final-byte-definition.jsonl`.
- Precompute and subagent compactions delegate to core. Native message views omit
  hidden reasoning/image blocks; actual usage and candidate-count scope are explicit.
- Additional live governing-lock/truncate/fallback/missing-key cases, sustained
  retention quality, and Codex runtime parity remain follow-up evidence.

## Reflexive

Applied `solid-loop` to the design friction notes:

- Missing project-local model profile: gap; user-root profile resolved this run;
  no project profile or unrelated global instruction was created.
- Function module registration: gap; resolved by the shipped hooks.json module entry.
- Print JSON event arrays: gap; handled by evidence readers.
- Broad scratch searches and working-directory mistakes: general tool-use slips;
  use exact experiment entrypoints and repository-relative edit cwd; no new rule.
- Changed upstream wording fixtures: gap; updated to the recovery contract and
  retained the state budget assertions.
- Upstream message handle reuse: misdirection in reference implementation;
  fixed in our adapter and documented in UPSTREAM.md with real restart evidence.

Commit, push, installation, and the independent review disposition are distinct
release events, reported through the dispatch lifecycle after this source check.

## Independent review follow-up: 0.30.17

The original review is retained at
`/tmp/straw-boss-jev-claude-review-20260920/review.md` and in the private release
evidence. The findings were reproduced before implementation: the `cd` path
fixture failed, existing-mode assertions failed, and all five symlink cases
failed. After repair:

- Python storage/renewal and instruction-quality checks: **46 passed, 155 subtests**.
- TypeScript suites: **40 passed**; library/hook typecheck and build passed.
- `cd ~/.straw-boss/dispatch && cat task.json` retains its pair with zero Jev
  requests; absolute dispatch paths and literal guidance filenames also retain.
- Explicit negative cases record that bare `cat task.json` and
  `f=CLAUDE; cat "$f.md"` remain unmatched. Universal provenance protection is
  not claimed; policy v3 fixes the recognized directory boundary only.
- Existing-mode, symlink (root, child directory, benchmark, lock, snapshot),
  hardlink, FIFO, and simulated foreign-owner cases pass. Reads/updates use
  the same descriptor-based private access, and original recovery stays exact.
- Benchmark rows are documented as sensitive raw records, including potentially
  printed credentials; they have no automatic expiry or redacted-export behavior.

No new live compaction or full-suite run was added for this focused follow-up.
The prior real compaction evidence and fixed-history measurements describe policy
v2; this boundary extension does not constitute a new savings measurement.
Review disposition: original **REQUEST CHANGES**, findings addressed at the
scoped test/documentation boundary; independent follow-up verdict pending.
Reflexive: the recognition and creation-mode assumptions were gaps closed in code
and its operation guide; shell helper invocation was a local tool-use correction.
