# Design

Use the canonical JSON policy and criteria and shared Python byte-accounting/storage helpers. A Codex adapter transforms response-item arrays and emits a fresh compacted replacement-history record into explicit copies; it never rewrites source rollouts. The existing Claude adapter remains independently owned.

Keep provider-native integration separate from replay: PreCompact and thread/compact/start expose no documented replacement-history return field. Verify this against installed protocol and current official docs before claiming a production hook. A hook that merely edits a persisted live rollout would not replace in-memory history and violates the copy-only scope.

For comparable scoring, reuse round 2 judging states and exact target envelopes with only criteria replaced. Evaluate governing-source locks after recording raw scores so the 44 pair comparison remains visible. A production adapter skips judging locked pairs. Retain round 2 recency inventory for controlled regression; separately test first/latest-six provider-message mapping.

Verification surface: adapter public functions, opt-in command, four real copied resumes, marker persistence test, byte comparison with shared helper, and exact reconstruction from originals.

## Friction Notes

- Tried: Read the project model-preference profile at its instructed path.
  Found: This checkout has no such profile; no delegation is needed, and benchmark model/effort are fixed by the preserved baseline.
  Led by: AGENTS.md routing.
- Tried: Search the existing graph for Jev symbols.
  Found: The graph omits the other worker's new untracked Jev files; direct reads of the named files establish the current implementation.
  Led by: Codebase Knowledge Graph instructions.
- Tried: Read vendor records.ts.
  Found: Pair collection lives in state.ts.
  Led by: none
- Tried: Send a progress message using intent update.
  Found: The dispatch CLI calls that intent inform.
  Led by: none

## Confirmed provider boundary

The user's parity requirement was confirmed before this limitation was known.
The main agent confirmed on 2026-09-20 that runtime parity is currently
unachievable on Codex 0.155.1. Deliver behavioural parity of criteria, policy,
gate and benchmark, the opt-in copy adapter and four-point replay; live
application parity remains a provider gap. Existing renewal ordering stays
unchanged because no loaded Codex hook can apply the candidate.

Evidence: installed `ThreadCompactStartParams` accepts only `threadId`;
[official hook documentation](https://learn.chatgpt.com/docs/hooks#precompact)
limits PreCompact output to the common continue/stop/UI fields. Preserved local
protocol: `/Users/weihung/.straw-boss/evidence/jev-codex-parity-round3/protocol`.
- Tried: Normalize every result as plain text or text-only blocks.
  Found: Real middle/late checkpoints include image blocks; text byte accounting excludes images like the shared Claude projection, while retained output keeps image blocks in their original order.
  Led by: Shared byte-accounting contract.
- Tried: Use unique session identities and instruction nonces for zero-cache resumes.
  Found: Four of eight initial resumes still reported 7040 cached input tokens; preserve those attempts and rerun the same history with fresh identities, accepting only explicit zero-cache usage.
  Led by: Dispatch zero-cache reality anchor.
- Tried: Reuse the shared recovery writer for explicit evidence destinations.
  Found: Concurrent privacy hardening scopes that writer to the Jev store; the copy command instead exclusively creates files in its own new private output directory, while the experiment owns its evidence writer.
  Led by: Reuse existing persistence helpers.

## Policy v3 follow-through

Re-read the shared policy after the Claude fresh-context review. Its canonical
hash is `sha256:96f92e7a660ae677ecd75ec46b08e25bf6fc43dd26adc42feb4457183db6aed4`.
Applying v3 to the same 44 scores produced identical candidate arrays at all four
checkpoints, so the existing zero-cache resumes remain valid for those arrays.
The benchmark was regenerated with v3 identity. Add regressions for the compound
relative read and serialized workdir; document arbitrary shell indirection and
a bare filename without source identity as identification limits.

The comparison preserves round 2's judging envelope and conservative recency
boundary. The production copy command consumes validated versioned scores; it
does not claim to run the Claude 25k/30k batching fitter or a live Codex hook.

## Independent review correction (F1/F2)

The review of bc4b604 requested changes. Its reproduced findings reopen the
storage and invalid-score checkpoints; the preserved scoring/gate evidence remains
valid. The confirmed contract already requires both behaviours.

Check three explanations independently: malformed score objects reach member
access before validation (predict AttributeError); replacing the output directory
redirects later pathname writes (predict archives in another directory); a leaf
symlink bypasses exclusive creation (predict overwrite). The review's executable
reproduction confirms the first two and rejects the third.

Use the shared jev_private ownership/open primitives for a dedicated new-copy
context. The caller supplies an existing current-user-owned parent with no group
or other write bits; open and validate it once, create/open the new output relative
to that descriptor, and keep the output descriptor for all three exclusive child
writes. A symlink swap before the output open fails closed; replacement after it
opens leaves every write attached to the pinned directory. This defines a trusted
parent boundary rather than treating new-directory mode alone as confinement.
Validate the scores mapping and each unlocked score mapping before member access;
malformed shapes enter the existing ValueError fallback.

Review-fix reality anchor: `tests/test_jev_codex_copy_review.py` failed with
10 failed / 1 passed before changes. Malformed pair/container shapes now produce
unchanged fallback artifacts; an output-path swap before directory open is
rejected, and a swap after the first child opens keeps all three artifacts in
the original pinned directory. Group-writable parents are rejected before output
creation. Existing store behaviour remains unchanged; the copy path reuses
jev_private's ownership and descriptor-relative child-open primitives.

## Review friction

- Tried: Treat exclusive new files beneath a 0700 pathname as confined output.
  Found: Directory-entry replacement redirects later pathname opens; a pinned
    directory descriptor is the required boundary.
  Led by: Initial design's copy-output rationale.
- Tried: Validate numeric score members without validating their container.
  Found: Lists, numbers and strings raise AttributeError before the fallback;
    both container levels must be dictionaries before member access.
  Led by: Initial score-validation implementation.

Both gaps are resolved by shared descriptor helpers, input validation and public
CLI regression tests. The independent review supersedes the initial self-review's
storage and malformed-score verdicts; the four-point measurement evidence remains
valid. Live Jev scores are observed samples: hashes and fixed-score application
are reproducible, while live judging scores, branches and continuation text may
vary on rerun.

## Second-review correction (R1/R2)

The first correction's resolved-parent string still allowed an intermediate
ancestor swap before the parent opened. Replace that approach with a component
walk from an open filesystem-root descriptor, using O_NOFOLLOW and dir_fd at
every step. Each ancestor is root/current-user owned; writable intermediate
ancestors require sticky-bit protection, and the immediate parent is user-owned
and has no group/other write bits. Physical paths contain no symlink components
or `..`. This POSIX owner/mode boundary assumes no extra ACL write grants and
excludes privileged/current-user adversaries. Previously opened directories stay
pinned even when their original names are moved.

Validate score numeric bounds using integer-safe comparisons before any float
conversion. The [0, 1] comparison rejects huge positive/negative JSON integers,
infinities and NaN without math.isfinite converting integers.

The new six red cases cover both score fields with positive/negative 10**400,
intermediate symlink substitution before opening, and a nonsticky writable
ancestor. Additional compatibility/confinement tests exercise sticky ancestors
and replacement after an intermediate component is pinned.

- Tried: Resolve a parent string, then protect only the terminal directory open.
  Found: Intermediate ancestors can change between resolution and opening;
    root-relative descriptor traversal is needed for the stated path boundary.
  Led by: First-review correction design.
- Tried: Call math.isfinite on every numeric score before checking its range.
  Found: JSON integers can exceed float range; direct integer-safe bounds reject
    them without conversion or a blanket exception handler.
  Led by: Numeric validation implementation.

Both gaps are resolved in the same private-copy and score-validation seams.
The earlier 504-test result applies to the first correction, not this final tree.
