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
| Avoid duplicate long-task injection | Public launcher test gives the worker a long CJK contract task and proves the TUI receives only the bounded start prompt plus its 256-bit marker. |
| Confirm extremely narrow delivery | Public launcher test renders the Claude transcript at 11 columns with only six visible lines and confirms the 43-character base64url SHA-256 marker without resending. |
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

Further reproductions captured why full-task transcript comparison and a long
hex marker were not valid proofs. The CJK case returned exit 1 when terminal
rendering changed `外層` to `外 層`. A bounded view could never contain the long
task even after two submissions, and an 11-column Claude pane could crop the
full hexadecimal marker from its visible transcript. The immutable contract now
owns the task body; the TUI receives a bounded start prompt with the same
SHA-256 encoded as a 43-character base64url value. Transcript matching still
removes all Unicode whitespace.

## Automated results

- Focused marker, CJK, retry, refusal, and Codex Plan tests — 19 tests passed.
- `python3 -m unittest tests.test_dispatched_agent_lifecycle_transport` — 67
  tests passed in 40.590 seconds.
- `python3 -m unittest tests.test_codex_plan_orchestration` — 15 tests passed
  during focused development.
- `python3 -m unittest tests.test_install_script` — 3 tests passed.
- `python3 -m unittest discover -s tests -p 'test_*.py'` — 98 tests passed in
  42.268 seconds before the `0.18.20` delivery bump.
- `bash -n scripts/install.sh` — passed.
- `shellcheck scripts/install.sh` — unavailable in the release environment; the
  earlier shellcheck result for the unchanged installer remains green.
- `python3 -m compileall -q scripts tests` — passed.
- `jq -e` for both plugin manifests — passed.
- `claude plugin validate .` — passed.
- `git diff --check` — passed.
- `openspec validate --all --strict` — unavailable in the release environment.

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
`0.18.13`; bounded-marker confirmation now bumps both to `0.18.20`. Commit,
push, and local-install evidence is reported separately at handoff so repository
verification does not claim external state before it exists.
