# Claude Jev adapter design

Contract: [spec.md](spec.md). Decisions: [decision.md](decision.md).

## Interfaces and ownership

- Vendor the upstream TypeScript library under `vendor/fast-jev-compaction/`,
  with its MIT license and exact source commit. Keep local changes documented.
- A Claude function-hook adapter owns activation, Jev transport, backend token
  measurement, recovery persistence, and compaction outcomes. Register it in
  the existing Claude `hooks/hooks.json` modules field; Python command hooks
  retain their current registration.
- Keep retention wording and thresholds in a shared data file so Codex can
  consume the same contract. Hash the exact canonical criteria JSON.
- A small Python persistence helper provides atomic user-private run records
  and a session-scoped state record. The Stop renewal guard consumes that state
  only for an opted-in Claude session with a nonempty key and a loaded hook.
- Preserve the current renewal module boundary, role adoption, and continuity
  record format. Disabled, missing-key, or unavailable-hook sessions use the
  existing renewal behavior.

The alternative of a separate upstream plugin plus a recorder would split the
gate, recovery write, and action across independent hook chains. A vendored
library with one adapter keeps that transaction and its tests in one place.

## Measurement investigation

Claude's `$.session.usage().context.tokens` is the previous backend response's
input-side usage. It cannot measure an uninstalled candidate. The native count
API can count structured messages before selection; actual usage must remain a
distinct field. The host uses an Anthropic API key or the existing Claude OAuth credential
(local credential file, macOS Keychain fallback) only at the official count
endpoint. Native message blocks are counted before and after; the larger live
input is the gate denominator. Actual next-request input is a separate
observation, persisted across restart. No candidate is selected on a character
estimate or missing backend count.

Disposable capability probe: `/tmp/straw-boss-jev-hook-probe/`. On Claude Code
2.1.278 the function module loaded and obtained live usage (458 input tokens),
but `$.session.authorize()` returned null both at SessionStart and turn.complete.
The probe is temporary and will not be installed or committed.

## Verification

Exercise the adapter through a mock engine for deterministic invariants, real
Jev responses against the durable Round 2 cases for retention, and real Claude
compaction for hook and backend accounting evidence. Repository pytest covers
renewal and storage. Installation stays opt-in.

## Friction Notes

- Tried: read the project-local model preference profile named by the project instructions.
  Found: that path is absent; the user-root profile and its active strategy exist.
  Led by: project AGENTS model preference routing.
- Tried: load a hooks TypeScript file without a hooks.json modules registration.
  Found: Claude loaded the plugin but did not execute its function module; explicit modules registration made it execute.
  Led by: none.
- Tried: parse the Claude print JSON output as a single result object.
  Found: this runtime emitted an array of typed events, including the final result.
  Led by: none.
- Tried: recursively search the prior scratch tree for benchmark measurement code.
  Found: regenerated CODEX_HOME caches dominated the results; exact experiment entrypoints provide the useful evidence.
  Led by: none.

- Tried: rerun upstream fixture expectations after changing the judging context and recovery note.
  Found: text-dependent fixtures changed; retain the semantic budget assertion and update the recovery contract wording.
  Led by: none.
- Tried: edit repository-relative paths from the vendored package working directory.
  Found: edits need the repository working directory, while package tests need the package directory.
  Led by: none.

- Tried: reuse upstream unchanged message handles across a real compaction and CLI restart.
  Found: the hook returned eight messages and the CLI reported compaction, but resume reconstructed dropped ancestors and sent 55,980 input tokens; fresh message identities fixed the persisted chain and a real restart used 1,795 input tokens while retaining the fixture invariant.
  Led by: upstream toSessionMessages handle reuse.

## Shipment decision

The user directed 0.30.16 commit, push and installation with activation off,
and deferred further live branch coverage to benchmark review. The main agent
owns an independent follow-up review and explicitly released it from the ship
checkpoint. Shell dotfiles remain unchanged.
