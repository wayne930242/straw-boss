# Busy-pane delivery verification (0.30.7)

## Behavior

A checkpoint reply is submitted once and resolves when Herdr returns a
`result.type: agent_prompted` receipt for the expected pane and provider, or
when the reply is observed in the transcript. The receipt follows writing both
text and Enter. A working pane queues it; idle/done/blocked submissions also
pass the existing lifecycle gate. Unknown pre-send states require transcript
evidence. Missing or incomplete evidence exits nonzero and preserves the
checkpoint bytes, reporting the observed receipt and transcript-read outcome.

`reply-to-worker.py` uses this evidence through the shared transport. The
launcher uses the same rule for its delivery marker and stops after an accepted
but unconfirmed submission. Its existing bounded startup-stall recovery stays
in place. `send-dispatch-message.py` already submits once and has no
confirm-then-resend loop, so its behavior is unchanged.

## Real-pane probes

Run on 2026-09-20 with Herdr client/server 0.9.0, isolated scratch dispatches,
Claude Code Sonnet low and Codex Luna medium. Each reply has two lines, a long
payload, and Traditional Chinese fixture data. The fixed cases use 3,662 or
more characters. Ready panes reported `done` (Herdr's unviewed idle state);
mid-turn panes reported `working` while handling a requested 90-second sleep.

| Case | Original 0.30.6 | Fixed 0.30.7 |
|---|---|---|
| Claude, ready | Not separately probed on the original version | Exit 0; resolved; one submission and one received identifier |
| Claude, mid-turn | Long reply: exit 1; unresolved; two received identifiers | Exit 0; resolved; one submission and one received identifier |
| Codex, ready | Existing compatibility covered by automated tests | Exit 0; resolved; one submission and one received identifier |
| Codex, mid-turn | Exit 1; unresolved; queue visibly contains reply and reply-retry; two received identifiers | Exit 0; resolved; queue contains one reply; one received identifier |

Claude displayed queued text but long replies exceeded the viewport. Codex
rendered only a few lines per queued message with an ellipsis. Both returned a
target-bound `agent_prompted` receipt and later consumed the submissions. This
makes full-message substring absence an unreliable resend trigger.

Raw evidence is retained at
`~/.straw-boss/evidence/reply-busy-pane-2026-09-20/`:

- `baseline-busy-codex-after-pane.txt` and
  `baseline-busy-long-claude-after-pane.txt`: original failure surfaces.
- `acceptance.jsonl`: real prompt arguments, raw Herdr responses and exit codes.
- `fixed-{idle,busy}-{claude,codex}-{before,reply,after-pane}.txt` and
  corresponding `status.json` snapshots: per-case CLI and checkpoint proof.
- `fixed-{claude,codex}-consumed.txt` and `received.txt`: post-tool consumption.
- `regression-red.txt`: both provider subcases fail on the original implementation.
- `suite-final.txt`: full-suite result on the completed change.
- `cleanup.json` and `{claude,codex}-closed.txt`: removed canonical scratch files
  and confirmed pane closure; snapshots remain only as evidence.

## Requirement coverage

| Requirement | Evidence | Result |
|---|---|---|
| Busy replies send once and resolve | Both real busy probes, acceptance receipts, status snapshots, receipt counts | pass |
| Idle replies remain functional | Both real ready probes and legacy transcript compatibility tests | pass |
| Ambiguous delivery fails without mutation or resend | CLI regression asserts exit, one prompt, diagnostics and exact original status bytes | pass |
| Later transcript visibility can confirm | Delayed-read test with wrapped CJK data | pass |
| Same launcher false negative is fixed | Busy accepted marker-hidden regression; ambiguous submission keeps pane without receipt or resend | pass |
| Other sender inspected | Single submission in send-dispatch-message; exercised during scratch control | pass |
| Plugin version | All three manifests set to 0.30.7 | pass |

## Review and automated verification

A fresh-context GPT-5.6 Sol low review found no actionable issues and passed
both contract and project-standard checks. Its independent full-suite run
passed 432 tests and 195 subtests; see `fresh-context-review.md` in the evidence
directory. The owning run also records its full-suite output in `suite-final.txt`.

## Scope and disposition

Local tests and real-pane evidence establish local behavior. Push, merge and
installation belong to the coordinating main agent. No repository changelog
exists; this report records the release behavior and verification.

The temporary profile/test-path lookup friction was a tool-use gap: the
existing global profile fallback and graph discovery resolved it. The
`solid-loop` pass requires no new instruction for that one-off lookup.

## Launcher revert (0.30.8)

0.30.7 also let the launcher accept an `agent_prompted` receipt from a
`working` pane. At launch, `working` means the agent is still booting, and a
booting Codex drops the typed task: a real launch returned `confirmed: true`
with an empty composer and no rollout file. 0.30.8 restores the 0.30.6
launcher, which requires the delivery marker in the transcript and resends on
its absence. `test_launcher_resends_when_a_booting_pane_accepts_but_drops_the_task`
fails on 0.30.7 and passes on 0.30.8. Checkpoint replies keep the 0.30.7
receipt rule, since a worker that reports `working` mid-turn queues input.
