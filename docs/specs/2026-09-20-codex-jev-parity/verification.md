# Verification

Evidence root: `/Users/weihung/.straw-boss/evidence/jev-codex-parity-round3`.
The main agent accepted the provider boundary and copy-adapter deliverable on
2026-09-20. Runtime parity was requested before that limitation was known.

| Requirement | Evidence | Result |
|---|---|---|
| Exact canonical criteria and current lock policy | Recomputed v4 criteria `0717ecfc...3ebe`; re-read v3 policy `96f92e7a...aed4`; identities in every benchmark row | pass |
| Ordinary sessions unchanged; missing/empty key silent | No live hook registration or renewal edit; subprocess tests for opt-out, empty and whitespace key; installed-copy smoke returns 0 with empty stdout/stderr and no files | pass |
| Governing, first and recent locks | Real four-point candidates retain identified governing pairs; all original recency indices preserved; v3 compound/workdir tests | pass |
| Universal governing-source identification | Arbitrary shell indirection and bare relative filename without serialized source identity remain uncovered, as on Claude | unknown |
| Pairing, text and reasoning preservation, recovery | Every real candidate preserves user/assistant and reasoning arrays; original indices/content reconstruct all four histories exactly | pass |
| Shared normalized byte accounting | Adapter calls shared pair_bytes for one normalized invocation and one text result; image bytes excluded, raw originals retained | pass |
| Real revised 44-pair comparison | Raw 34 drop, 7 keep, 3 truncate; all raw values/deltas in per-pair.csv; after locks 26 drop, 17 keep, 1 truncate among these 44 | pass |
| Governing scores crossing 0.5 | Contract scores 0.65/0.68, 0.64/0.68, 0.68/0.68; instruction scores 0.53/0.52, 0.54/0.47, 0.53/0.41; locks preserve instruction reads that wording would truncate | pass |
| Real truncate decision | table-late call_wgiG1gKXbhvb4mSXfV6VSJJd selects drop_result at 0.50/0.24 | pass |
| Real long-result truncation | Selected result is only 156 characters, so no bytes removed; longer-prefix and image preservation exercised only by synthetic tests | unknown |
| Zero-cache backend 10% gate | Eight accepted real resumes all cached_input_tokens=0; 0.00370%, 25.43144%, 36.49757%, 0.00400% | pass |
| Release-middle interaction | All three formerly unlocked pairs now governing-source locked; unchanged candidate selects fallback instead of round 2's 14.96% apply at 10% | pass |
| Table-early coherence regression | Verbatim current pruned answer retains both new-file paths, oxlint/dprint and Git-tracked-file caveat before browser QA; missing-contract assertion absent | pass |
| Codex parent-chain persistence | First and second process resumes both see replacement marker and report old marker ABSENT, with original history item/call IDs retained | pass |
| Benchmark recovery, per-request costs, provenance and qualitative outcome | Four schema-validated JSONL records, recovery originals, source cut/hash, model/effort, zero-cache evidence, latency definitions and explicit semantic assessment | pass |
| Actual live history application and event-trigger parity | Codex 0.155.1 public PreCompact cannot replace history; no live application attempted | unknown |
| Live built-in fallback and post-compaction renewal parity | Provider limitation; ordinary existing renewal ordering preserved | unknown |
| Copies only and source immutability | Source/prefix hashes match sources.json; isolated CODEX_HOME installs/resumes; copied authentication removed | pass |
| Opt-in local installation | Isolated Codex plugin installation reports 0.30.18; adapter/config hashes match source; live config untouched | pass |

The small differences for identical early/release histories are replay overhead,
not pruning. Four initial cache-hit attempts are archived and excluded from gate
measurements. Applying final policy v3 produced identical candidate arrays to
those resumed before the policy amendment.

## Review disposition

Standards self-review: pass. English source/documentation, scoped modules,
private new output directories, exclusive file creation, silent opt-out, no
changes to other workers' files except the coordinated three-manifest version
bump. No independent reviewer was launched in this session.

Spec self-review: pass for the explicitly accepted copied-history deliverable;
live application, automatic fallback/renewal and real long-result shortening
remain unknown. The comparison retains round 2's 32k judging envelope and
conservative Codex recency grouping; it does not claim Claude production fitter
or native message-granularity parity. These limits are documented in the user
guide and evidence result.

The qualifier "specific-regression-absent" describes one continuation comparison,
not a general semantic-equivalence verdict. Human appropriateness testing is not
applicable to this CLI replay adapter; the continuation assessment was performed
by the implementer and has no user verdict attached.

## Reflexive pass

Applied `solid-loop` to the design friction notes:

- Missing project model profile: gap outside this bounded task; no model selection
  or delegation occurred. Baseline model/effort came from the authorized experiment.
- New Jev symbols absent from graph: transient indexing gap; named-file fallback
  supplied the current source, no persistent instruction change needed.
- Guessed vendor filename and dispatch intent: general tool-use slips; corrected
  to state.ts and inform, no instruction change.
- Image-containing results: gap resolved by adapter support and regression test.
- Cache hits despite nonce: gap documented with the preserved retry procedure and
  explicit zero-cache acceptance; no inferred token savings accepted.
- Shared storage writer narrowed by concurrent change: gap resolved by exclusive
  copy-output creation and CLI privacy tests, preserving the shared store's scope.

No global memory or skill files changed.

## Delivery evidence

Local automated tests, real resume evidence, isolated installation, commit/push
and remote state are separate claims. No live deployment or browser UAT is claimed.

- Final full suite: `uv run --with pytest pytest -q tests` — 493 passed,
  209 subtests passed in 252.21 seconds.
- Focused adapter and English-documentation checks: 58 passed, 148 subtests.
  The adapter-only suite contains 22 tests, including the final stale-score
  fallback and private copy-output checks.
- Real command smoke: table-late CLI candidate equals the measured candidate
  exactly. Installed adapter/config file hashes match source; no-key invocation
  is silent.
- `git diff --cached --check`: pass. Version manifests agree at 0.30.18.
- Commit/push reference and remote verification are recorded in the dispatch
  completion and private evidence `delivery.json` after publication.
