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
