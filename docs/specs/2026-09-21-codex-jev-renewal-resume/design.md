# Design investigation

Decision contract: [decision.md](decision.md). The user confirmed the 200k / Jev-first / ordinary-fallback ordering.

## Candidate seam

Keep the Stop guard responsible for the renewal trigger and the detached
deliverer responsible for waiting until the live turn ends. A Codex adapter
behind that delivery boundary can snapshot the final rollout, score and measure
the candidate, persist recovery, and select resume or ordinary clear. This
avoids scoring an incomplete tool exchange while the original turn is running.

Compare this with running all work synchronously in the Stop hook: the detached
boundary avoids a long hook timeout and uses the same idle-pane coordination
as ordinary renewal. A fallback continuity payload and role metadata must be
available before stopping the original process. Candidate application and
fallback consumption must have distinct evidence.

## Remaining executable questions

1. Can isolated copied Codex resumes obtain comparable zero-cache backend
   input counts without continuing task actions? Reject inconclusive probes and
   preserve their measurements separately from the actual resumed session.
2. Can the deliverer exit and restart Codex in the same pane while preserving
   launch configuration, and recover ordinary renewal after a failed restart?
3. Does the resumed rollout contain the exact candidate replacement history,
   with role adoption and loop suppression still working?

The contract authorizes these runtime probes and the final real-pane test.
Neither manual replay evidence nor unit-test mocks establish live application.

## Friction Notes

- Tried: Locate the instructed project-local model preference profile.
  Found: `skills/managing-model-preferences/model-preference-profile.md` is absent; the user-root profile exists. No review model has been selected yet.
  Led by: Project model-preference routing.
- Tried: Discover code through the available codebase graph tools.
  Found: This session's tool catalog exposes no codebase-memory graph or tool-search capability. The contract's explicit module paths and direct source reads provide the current evidence.
  Led by: Project code-discovery instructions.
- Tried: Locate project-specific `.claude/skills/` and `docs/adr/`.
  Found: Both directories are absent; `AGENTS.md`, `CONTEXT.md`, and existing `docs/specs/` provide project guidance.
  Led by: Project guidance interoperability and leveraging-tasks.

## Implementation design

`jev_codex_renewal` owns the transaction; the existing renewal command records
fallback continuity and schedules it after the turn ends. Activation changes only
the Codex branch. The priming hook uses candidate history on successful resume
and the existing continuity payload on clear. The existing role adoption and
renewed-session threshold exemption remain in force.

`jev_codex_scoring` fits shared criteria into production-sized requests, skips
locked pairs, validates scores, and returns raw request metrics. Its budget
estimate follows the vendored production estimator; it does not measure savings.
`jev_codex_probe` runs isolated read-only copied resumes with task tools disabled,
fresh accounting prefixes, and a one-word accounting prompt. It rejects tool
calls and intervening compaction. Copies use the current model/effort and remove
the temporary auth copy in a finally block. The gate denominator is the larger
of baseline probe input and live source input, so omitting live tool schemas in
the accounting copies cannot inflate the percentage of live context saved.

`jev_codex_transport` captures the caller's foreground process, session and
terminal fingerprint before detaching; it preserves supported launch options.
After preparation it validates the idle original and its unchanged rollout,
registers a new private UUID, quits, and runs `codex resume` through a small
exec client. A private Unix socket carries the inherited environment in memory,
including session-local activation; shell commands and recovery artifacts carry
no API key. Unknown launch switches select ordinary renewal.

Production prototypes and final probes use a dedicated sibling pane. The first
isolated accounting probe returned 81,524 input tokens, zero cache, five output
tokens, and no tool call or compaction. Actual candidate application still needs
the real-pane evidence below.

- Tried: Let Herdr detect a Codex session in a scratch CODEX_HOME with hooks disabled.
  Found: It detects the provider but has no conversation fingerprint; the scratch runtime needs the native Herdr session hook too.
  Led by: Isolation of the real-runtime probe.

- Tried: Add a trust table after accepting the scratch workspace trust prompt.
  Found: Codex had already persisted that table, so the duplicate prevented startup; regenerate the dedicated scratch config once.
  Led by: Runtime fixture setup.
- Tried: Run the vendored npm test suite immediately.
  Found: This checkout has no installed vendor dependencies; use npm ci before tests/build.
  Led by: Dispatch verification requirements.

- Tried: Resume a synthetic fixture without ordinals.
  Found: Codex 0.155.1 paginated rollouts require every row ordinal; the production replacement_rows helper already assigns them.
  Led by: Runtime fixture setup.

- Tried: Copy a fixture by editing only session_meta.id and use a qualified tool name.
  Found: Current rollouts also carry session_id, and raw function names exclude the namespace prefix; regenerate the fixture through the production clone helper with a valid raw name.
  Led by: Runtime fixture setup.

## Review corrections

The independent review requested changes for three reproduced defects. Live
requests now carry exact invocation and result content; oversized results are
covered by bounded chunks and the maximum retention score keeps any needed
chunk's complete pair. Both ordinary fallback and application revalidate source
and request identity; the outer handler also retains the original transaction
identity instead of accepting a newer pending session. Probe credential creation
now occurs inside the cleanup try after rollout preparation. Each reproduction
has a regression test.

- Tried: Judge retention with the production history view and result lengths.
  Found: Equal-length different outputs produced identical requests, so result-sensitive retention was impossible.
  Led by: Reuse of the vendored result-omitting state view.
- Tried: Allow ordinary clear after any preparation exception if a pending record matched the live pane.
  Found: A newer pending session could pass that check; fallback authority must remain bound to the original transaction.
  Led by: Broad failure-to-ordinary-renewal requirement.
- Tried: Copy probe credentials before constructing the candidate rollout.
  Found: An exception before the cleanup try retained the temporary credential; create it inside the protected lifecycle.
  Led by: Probe implementation.
- Tried: Use the JSON Herdr helper for pane run.
  Found: The installed CLI returns empty stdout on successful pane run; use its checked raw response and confirm the actual resumed identity separately.
  Led by: Existing Herdr helper reuse.

- Tried: Place the launch socket inside an arbitrarily deep Jev store.
  Found: AF_UNIX pathname limits reject long pytest or configured roots; use a short, unique 0700 temporary directory and delete it after handoff.
  Led by: Private socket design.
- Tried: Run a full suite while the final interruption class was still being added.
  Found: Collection imported the earlier runtime while dynamic script loading read the newer caller; the full suite must report against the frozen final source.
  Led by: Concurrent verification scheduling.
- Tried: Send the coworker rereview request with peer intent inform.
  Found: Peer delivery accepts question or answer; the rejected request was not submitted and the corrected question was accepted once.
  Led by: Dispatch message CLI help.

Final review correction: source advancement uses RenewalInterrupted even if both
archive and cancellation-record writes fail. The deliverer catches this before
its ordinary-fallback branch. The reviewer reproduced the combined failure, then
closed F2 after the new transaction-plus-deliverer regression passed.
