# Verification

| Requirement | Evidence | Result |
|---|---|---|
| Codex coworker from Codex and Claude parents inherits actual tier | Facade integration matrix covers both providers and three tiers | pass |
| Review-only work scope retains coordination permissions | Unrestricted Herdr start argument plus review-only contract assertion | pass |
| Narrower parent tier and unknown tier stay conservative | Recorded-tier matrix and legacy-process tests | pass |
| Raw child arguments cannot widen permissions | Launcher rejects bypass, sandbox aliases, profile and arbitrary config | pass |
| Notification routing stays compatible | Existing coworker parent/root status tests | pass |
| Live status from real Codex coworker | coworker-permission-review reported progress, findings, and terminal status from its own Herdr pane | pass |

Focused verification after review fixes: 41 passed, 30 subtests passed, including exact effort-config rejection. The original facade regression and both review findings failed before their respective fixes and passed afterward.

The first full suite passed 561 tests and 232 subtests. The final full suite passed 562 tests and 238 subtests after review corrections (`uv run --with pytest pytest -q tests`, 166.60 seconds). Fresh-context reviewer disposition: Standards PASS, Spec PASS after fixing both initial blocking findings. The reviewer verified compact option/conflict/terminator coverage and a real default-Claude launch followed by the coworker launch.

Live evidence is a Codex parent launching a Codex coworker, with real progress, message and terminal status delivery through Herdr. Claude-parent behavior is exercised at the executable public CLI seam with fake Herdr; no live Claude-parent run is claimed. Restricted tiers remain subject to their parent's sandbox and approval policy.

Review reference: `~/.straw-boss/dispatch/archive/straw-boss--coworker-permission-review.status.json`. The reviewer pane was closed successfully and its lifecycle records archived.

## Reflexive

Graph-tool/profile availability and guessed file/glob attempts are tool-environment gaps; existing fallback rules cover them. No durable instruction change is warranted. The implementation resolves the permission-propagation gap. Compact-option inference and default-Claude inference gaps were corrected in code and regression tests; no new agent-system rule is needed.
