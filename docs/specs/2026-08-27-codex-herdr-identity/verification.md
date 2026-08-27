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
| Confirm initial task delivery | Public launcher test swallows the first Codex prompt, observes the retry in visible transcript, and only then receives a launch receipt. |
| Confirm bounded long-task delivery | Public launcher test exposes only the final 256 characters of a long CJK task and observes its SHA-256 tail marker without resending. |
| Tolerate CJK terminal wrapping | Focused matcher test inserts whitespace inside `外層` and confirms whitespace-insensitive presence. |
| Refuse false launch success | A two-miss launcher test proves the pane is closed and no receipt exists for `confirm` to consume. |

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

The prompt-delivery regression initially failed because the launcher returned
success after exactly one prompt without issuing any transcript read. The red
assertion observed one prompt where two were required. After implementation,
the first-miss case retries once and succeeds; the two-miss case fails after the
second bounded poll window and removes the pane.

Two further reproductions captured why full-task transcript comparison was not
a valid proof. The CJK case returned exit 1 when terminal rendering changed
`外層` to `外 層`. The bounded-view case failed after 21.096 seconds because a
256-character transcript tail could never contain its much longer task, even
after two submissions. The implementation now appends the full task SHA-256 as
an ASCII tail marker and removes all Unicode whitespace during comparison.

## Automated results

- Focused marker, CJK, retry, refusal, and Codex Plan tests — 19 tests passed.
- `python3 -m unittest tests.test_dispatched_agent_lifecycle_transport` — 62
  tests covered by the final full-suite run.
- `python3 -m unittest tests.test_codex_plan_orchestration` — 15 tests passed
  during focused development.
- `python3 -m unittest tests.test_install_script` — 3 tests passed.
- `python3 -m unittest discover -s tests -p 'test_*.py'` — 93 tests passed in
  49.729 seconds after the `0.18.14` delivery bump.
- `bash -n scripts/install.sh` — passed.
- `shellcheck scripts/install.sh` — passed without findings.
- `python3 -m py_compile` for three transport scripts and the changed lifecycle
  test module — passed.
- `jq -e` for both plugin manifests — passed.
- `claude plugin validate .` — passed.
- `git diff --check` — passed.

## Live observation and residual boundary

Read-only inspection of local Herdr 0.8.0 confirmed that live Claude records
contain `agent_session`, while the observed Codex records contain `pane_id`,
`terminal_id`, and `agent: "codex"` without `agent_session`.

No new live Codex worker was launched for this verification. The automated public
CLI seam covers delayed startup, retry, refusal, receipt, confirmation, and
transport without modifying an operator's active Herdr layout. `terminal_id`
remains a live routing fingerprint, not a Codex thread id; interactive
`codex exec resume` is deliberately outside this change.

The earlier identity delivery bumped both plugin manifests to `0.18.12` and
added the repo-owned installer. Full-task transcript confirmation bumped them to
`0.18.13`; bounded-marker confirmation bumps both to `0.18.14`. Commit, push,
and local-install evidence is reported separately at handoff so repository
verification does not claim external state before it exists.
