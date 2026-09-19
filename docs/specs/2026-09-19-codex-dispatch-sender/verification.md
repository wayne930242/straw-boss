# Verification

| Requirement | Evidence | Result |
|---|---|---|
| Caller thread owns Codex status and messages | New CLI regressions failed on the original implementation: background caller wrote status and sent a message from the same pane. They pass after the sender check. | pass |
| Rejection preserves existing records; worker and cancellation continue | `test_codex_dispatch_sender.py` checks byte-preserved status and existing ledger, no Herdr prompt, missing caller/live identity, null/pinned ids, real worker notification and main cancellation. | pass |
| Contract belongs to opening task | Launcher regression failed while the contract was in `developer_instructions`; it now asserts provider arguments omit the pointer and the first delivered prompt contains it. | pass |
| Both live status addressing routes check ownership | Instruction-path and canonical `plan_id` plan/task regressions reject the background thread; legacy plan ownership regression also passes. | pass |
| Existing dispatches use the installed guard | Read-only validation against the live n7 legacy null-id instruction accepts its actual caller and rejects a controlled different caller id. Post-install launcher resolution is recorded in the dispatch completion evidence. | pass |

Focused regression: 5 tests and 6 subtests passed. Adjacent status/message suite: 64 tests passed. Launch, coworker, takeover and resumed-thread suite: 100 tests and 6 subtests passed. Final full suite with release metadata: `uv run --with pytest pytest -q tests` passed 418 tests and 183 subtests in 192.37 seconds. `git diff --check` also passed.

## Independent review

Fresh-context review by a read-only Codex coworker (`gpt-5.6-sol`, low) returned Standards PASS (zero findings) and Spec PASS (zero findings). The reviewer independently exercised the sender, status/recovery and launch suites. Its completed instruction and verdict are archived at `~/.straw-boss/dispatch/archive/straw-boss--n7-sender-review.{json,status.json}`; the coworker pane was closed and the instruction archived.

## Runtime and release boundary

The live read-only checks do not mutate any plan state. Existing 0.30.3 contracts with `--prefer-installed` receive the guard after installation; previously injected developer instructions remain in those live sessions. The prompt-isolation change applies to new launches. Direct calls to an old cached script or an explicit old `STRAW_BOSS_PLUGIN_ROOT` override continue using that old implementation. A Herdr build that cannot expose the live Codex thread is refused before writes.

Historical memory consolidation used an ephemeral thread; its exact command transcript was unavailable. The observed failure artifacts, config inheritance in upstream source, and red/green CLI tests establish the supported mechanism without claiming a replay of that historical process. Deliberate environment forgery and direct filesystem writes are outside this cooperative identity contract.

## Reflexive

Applied `solid-loop` to the friction notes: Python executable choice, quoted shell URLs, and test import setup are general tool-use slips (gap; no instruction placement needed). The existing graph omitted known production symbols (gap; direct file inspection supplied the evidence). The absent local preference profile was resolved with the existing user-level profile (gap; no repository preference change). Fake Codex identities were resolved by this change (gap). No skill or project-rule expansion is needed.
