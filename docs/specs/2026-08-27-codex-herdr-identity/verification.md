# Codex Herdr identity verification

Date: 2026-08-27

## Requirement evidence

| Requirement | Evidence |
|---|---|
| Launch Codex without `agent_session` | Public launcher test omits the field, records `terminal_id`, confirms successfully, and preserves `session_id: null`. |
| Keep Claude session binding | Delayed-session launcher test polls only for Claude and confirms the preassigned session; existing Claude transport corroboration tests remain green. |
| Bind Codex live transport | Message-routing test accepts the exact pane, `agent: codex`, and terminal id. |
| Fail closed on replacement | Negative tests reject a different terminal id and a different provider before any prompt call. |
| Preserve coordinator and coworker routing | Main-agent provider-fingerprint requirements, Codex Plan routing, and same-worktree coworker tests pass. |

## TDD evidence

The initial Codex regression omitted `agent_session` from fake Herdr after the
first prompt. Before the implementation change it failed after the production
15-second deadline with:

```text
launched agent did not expose agent_session.value within 15s after its first prompt (last status: 'idle')
```

Two downstream red cases then exposed the schema and transport assumptions:

- confirmation converted JSON null into the string `"None"`;
- shared transport rejected Codex with `dispatch instruction has no worker session fingerprint`.

The implementation was changed only after each boundary had a reproducing test.

The installer slice first failed at its public command boundary because
`scripts/install.sh` did not exist (exit 127), while both READMEs lacked the
documented command. After implementation, fresh-install, stale-version update,
and bilingual documentation cases passed against stateful fake provider CLIs.

## Automated results

- `python3 -m unittest tests.test_dispatched_agent_lifecycle_transport` — 60
  tests passed during focused development.
- `python3 -m unittest tests.test_codex_plan_orchestration` — 15 tests passed
  during focused development.
- `python3 -m unittest tests.test_install_script` — 3 tests passed.
- `python3 -m unittest discover -s tests -p 'test_*.py'` — 89 tests passed in
  19.212 seconds after the final installer lint fix.
- `bash -n scripts/install.sh` — passed.
- `shellcheck scripts/install.sh` — passed without findings.
- `python3 -m py_compile` for the three changed scripts and two changed test
  modules — passed.
- `jq -e` for both plugin manifests — passed.
- `claude plugin validate .` — passed.
- `git diff --check` — passed.

## Live observation and residual boundary

Read-only inspection of local Herdr 0.8.0 confirmed that live Claude records
contain `agent_session`, while the observed Codex records contain `pane_id`,
`terminal_id`, and `agent: "codex"` without `agent_session`.

No new live Codex worker was launched for this verification. The automated public
CLI seam covers launch, receipt, confirmation, and transport without modifying an
operator's active Herdr layout. `terminal_id` remains a live routing fingerprint,
not a Codex thread id; interactive `codex exec resume` is deliberately outside
this change.

The subsequent delivery request bumps both plugin manifests to `0.18.12` and
adds the repo-owned installer. Commit, push, and local-install evidence is
reported separately at handoff so repository verification does not claim
external state before it exists.
