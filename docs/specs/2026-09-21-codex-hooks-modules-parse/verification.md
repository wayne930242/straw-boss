# Verification

Baseline a41bf1d (0.30.23). Private evidence root:
`~/.straw-boss/evidence/codex-hooks-modules-parse/`.

| Requirement | Evidence | Result |
|---|---|---|
| Codex parses its hook configuration | Baseline hooks/list: modules warning and zero Straw Boss entries. Staged real Codex 0.155.1 plugin install: three entries and no warnings/errors (staging.json). Regression first failed, then all three tests passed. | pass |
| Hooks run through provider discovery | Staged real codex exec session 01a0c224-3c60-7c90-817a-97f9d6ff7387 contains the exact SessionStart orchestrator stance as a developer message; response HOOK_PROBE_OK. Staged app-server turn 01a0c226-d3b5-7771-b65c-46f764396723 emits hook/completed for SessionStart and both Stop hooks with status completed (staging-turn.json). All three command wrappers also execute with the installed-root environment in regression tests. | pass |
| Claude retains command hooks and Jev module | Claude manifest unchanged; parity regression compares every command. Actual installed Claude 2.1.278 debug log records straw-boss@straw-boss loaded with session.start, session.compact, turn.complete, and session.start settled. | pass |
| Establish parse-failure impact and window | baseline.json proves all Straw Boss hooks omitted while other plugins remain. Source introduction 2d8998e, 2026-09-20 11:52:13 UTC, version 0.30.16; all releases through 0.30.23 retain modules without override. | pass |
| Full suite | 557 passed, 210 subtests passed in 194.33s; pytest.log. Focused new/quality suite: 39 passed, 149 subtests. | pass |
| Independent review | Fresh-context Sol low coworker codex-hooks-parse-review: Approve; Standards and Spec pass with no blocking findings. | pass |
| Ship and verify the normal installed plugin | Release 06572ec pushed to origin/main; standard installer completed on retry. Both provider caches report 0.30.24 and match source manifests/hooks/scripts. installed-final.json shows three trusted/enabled hooks, no warnings/errors; installed-turn.json records all three hook/completed events from the normal 0.30.24 cache. claude-installed.debug records module loading and session.start completion from its 0.30.24 cache. | pass |

## Impact boundaries

The affected source versions are 0.30.16 through 0.30.23 on Codex 0.155.1.
An installed session loading that definition loses SessionStart priming, the
report-before-stop guard, and the 200k renewal guard from this plugin. User hooks
and other plugins remain available. Launch-time contract injection is independent.
The exact first local installation time and every historical session's state
are unavailable; source introduction is not proof of continuous local outage.
The supplied 2026-09-21 03:59 UTC launch failure and this run's baseline establish
installed exposure. Existing sessions need a fresh load after installation.

No evidence connects the separate Herdr agent-start timeout to parsing. This
run's app-server and exec probes completed despite the baseline parser failure
being recoverable at plugin load. It is not claimed as a timeout fix.

## Trust and live boundaries

The new Codex hook path has new trust keys. Codex lists untrusted hooks but skips
execution until their exact hashes are trusted. The staged session uses three
scoped persisted trust entries, not a global hook-trust bypass. The normal installation received only the three reviewed-definition trust
hashes through config/batchWrite; installed-final.json confirms persisted trust. The installer itself retains the provider's trust workflow.

SessionStart and both Stop executions are directly observed in native provider
events. Guard decisions are covered by existing lifecycle and renewal tests. This task does not repeat full live 200k renewal or Jev compaction.
Claude live proof confirms module loading with Jev disabled for the probe.

## Reflexive pass

Solid-loop disposition: graph-tool availability and missing project profile are
local environment gaps already recorded in the related renewal verification;
no project-wide rule is changed. Creating CODEX_HOME before CLI use is a general
tool-use correction, requiring no agent-system placement. The peer inform rejection
was resolved by retaining the result in the shared artifact; peer intent rules
already live in asking-peer-agents, so no new rule is needed. Trust is an existing
README installation requirement and is exercised explicitly here.

## Final installation evidence

Release 0.30.24 installed and verified on 2026-09-21 at 04:10 UTC.
The first marketplace refresh failed on a temporary Git pack; a normal retry
completed without source or installer changes. release-proof.json records final
cache paths, trust, and native execution timestamps. Existing active sessions
need restart to load the fixed registration. Antigravity was absent and skipped.
The installer retry is an environment gap resolved by normal retry; no new rule
is needed. The review coworker approved the completed suite and all three native
hook events, then its pane was closed and lifecycle artifacts archived.
