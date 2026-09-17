# Verification: context renewal

Spec: [spec.md](spec.md).
Design: [design.md](design.md).

## Anchor 1: unittest

`python3 -m unittest discover -s tests` ran 386 tests on the final change-set and passed.
`tests/test_context_renewal.py` and the affected lifecycle and agy suites were re-run after the later fixes and passed.

## Anchor 2: live Herdr run

Sessions loaded the plugin from this checkout: Claude through `--plugin-dir`, Codex through an isolated `CODEX_HOME`, and Antigravity through workspace hooks.
The installed plugin (0.27.1) stayed untouched.

| Requirement | Evidence | Result |
|---|---|---|
| 1 Trigger | Claude turns ended at 421k and 385k, Codex at 206k, and agy above 200k; each was blocked with the renewal reason. Turns below the threshold (agy at 186k, Codex at 194k) ended normally. | pass |
| 2 Continuity record | `~/.straw-boss/renewal/pane-<pane>.json` held the role, payload, and instruction paths for Claude standalone, worker, and main; Codex standalone and main; and agy standalone. The Claude worker's progress log gained a checkpoint note. | pass |
| 3 Notice | One `Context renewal: record … clears after the turn ends.` line appeared, with no approval question (Claude pane; Codex rollout). | pass |
| 4 Clear in Herdr | `/clear` followed by the continuation prompt landed in the session's own pane for all three providers. | pass |
| 4 Clear outside Herdr | Unit test only: the notice asks the user to run `/clear`. | unknown |
| 5 Injection, role priming, consumed once | The record was consumed by the new session id; each session continued its recorded next action (Claude: summary state; Codex: wrote `paranephritis`, then `codex waiter done`; agy: resumed from the record). Consumed-once, other-pane, and other-provider cases are unit tested. | pass |
| 6 Main agent continuity | Claude and Codex: `main_agent_session_id` was adopted with a `context-renewal` entry, the orchestrator record was re-keyed with the same scope, and worker `done` reached the renewed main agent, which acted on it. Codex delivery needed Herdr's Codex session hook, which is absent in the isolated test home; it was reported by hand, as `~/.codex/herdr-agent-state.sh` does in the real home. Agy main agent: not run. | pass (Claude, Codex); unknown (agy) |
| 7 Dispatched worker continuity | Claude: `session_id` was adopted and the renewed worker's `send-dispatch-message` was accepted by the main agent. Codex and agy workers: not renewed live (Codex quota; agy scoped down for cost). | pass (Claude); unknown (Codex, agy) |
| 8 Standalone worker | Claude, Codex, and agy each renewed with no dispatch record. | pass |
| 9 User input during renewal | Claude: a message queued during renewal was answered (`42`) by the renewing session before the clear, not by the renewed session. Codex and agy: not run. | pass on Claude under the amended behavior 9; unknown (Codex, agy) |
| 10 Backstop | Owned by the main agent in `weihung-user-claude`. | not in this task |
| 11 Compaction priming | Priming with no record is unchanged; existing lifecycle tests pass. | pass (unit) |

## Deviations

- Behavior 9: Claude Code dequeues a message submitted mid-turn into the same session before Herdr reports idle, so the renewing session answers it and the message is not lost. Meeting the spec wording would require holding user input across the clear, which neither Herdr nor Claude Code exposes.
- A dispatched worker's checkpoint is a progress-log note plus the pending renewal record, which the stop guard accepts; no status value was added.
- `/effort low` sent during the Claude live run wrote `modelSettings` into `~/.claude/settings.json`; the key was removed right away.

## Fresh-context review

A read-only review of `49d467c..HEAD` found that outside Herdr, a record keyed only by the working directory could be claimed by an unrelated later session in that directory.
Fixed: outside Herdr, only a `source: clear` SessionStart within 30 minutes of the record claims it, so an agy session outside Herdr never auto-injects; this case is covered by a new unit test.
Its other findings were not changed: the agy guard blocks once per turn by design, and the model-supplied `--session-id` only affects matching inside the same pane.

## Gaps

- Agy main-agent and worker adoption, Codex worker renewal, and behavior 9 on Codex and agy were not exercised live.
- The agy context measurement reads an undocumented protobuf in its conversation DB.
- The plugin is not installed and not pushed; both wait for user authorization.
- Anchors 3 and 4 run 7 days after installation and stay with the main agent.

## Reflexive

Friction notes in [design.md](design.md#friction-notes):

- Codex kills `nohup … &` at turn end: gap. Recorded in design; no skill currently instructs backgrounding from Codex.
- agy ignores the Claude-format root `hooks.json`: gap. Fixed in code; README install notes unchanged.
- agy transcript has no token counts: gap. Recorded in design.
- agy plain-text SessionStart output: gap. Fixed in code; the design notes that injection must be proven through a side effect or `cli.log`.
- `/effort low` persists globally: gap. Recorded in design.

`solid-loop` was not invoked: every note is a provider fact with no misleading skill line, and applying them to skills is left to the main agent.
