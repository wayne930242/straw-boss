# Codex Herdr launcher QA

Date: 2026-08-26

## Scope and environment

- Current Straw Boss worktree launcher and status reporter.
- Herdr interactive dispatch from main pane `w3:p2` in tab `w3:t2`.
- Codex CLI 0.149.1, `gpt-5.6-sol` with low reasoning effort.
- Smoke tasks were read-only and made no project changes.

## Findings resolved

1. `herdr agent start` can return non-zero while leaving a recoverable blocked
   agent. The launcher now verifies that exact live state before sending Enter;
   unrelated start failures retain their error and close the worker pane.
2. Superseded on 2026-08-27: the earlier delayed-session diagnosis was
   incorrect. Herdr 0.8.0 does not expose `agent_session` for Codex. The launcher
   now waits for and validates that field only for Claude; Codex records Herdr's
   `terminal_id` and reported agent kind. See
   `docs/specs/2026-08-27-codex-herdr-identity/`.
3. A fast worker can report terminal status while its instruction is still
   pending confirmation. The status reporter now waits only for the bounded
   pending-without-worker-pane condition; sender pane/provider-fingerprint
   mismatches still fail immediately.
4. Herdr 0.8.2 exposes `done` as a terminal agent state. Completion smoke waits
   use Herdr's default `idle`/`done`/`blocked` set.
5. Codex does not set `CLAUDE_PLUGIN_ROOT`, so hook commands that required it
   resolved to `/scripts/...` and exited 127. Both hooks now fall back to the
   plugin working directory while retaining Claude Code's explicit root path.
   Superseded on 2026-08-27: that fallback resolved against the *session's* cwd,
   not the plugin directory, so it exited 127 in a real Codex session and could
   execute an unrelated `scripts/<same-name>` from the user's repo. Both hooks
   now require an explicit `CLAUDE_PLUGIN_ROOT` and report a skip instead.
6. Added on 2026-08-27: Herdr can accept an initial Codex task prompt while MCP
   startup is still active without the text reaching the TUI transcript. The
   launcher now polls transcript evidence, retries once after a full miss, and
   refuses a receipt after two misses.
7. A dispatch task was already present in the immutable mandatory contract, so
   pasting the full task into Claude duplicated context and could be folded by
   the TUI. The launcher now sends a bounded start instruction plus a digest
   marker while retaining the full task only in the contract.
8. With the main, completed database worker, and API worker visible together,
   the API pane was 11 columns wide. The earlier hexadecimal marker could be
   cropped out of the visible transcript. The marker is now the same SHA-256
   encoded as a 43-character base64url value, which was confirmed live in that
   narrow pane before the launch receipt was written.

## Live smoke evidence

- First smoke launched successfully without `--dangerously-bypass-hook-trust`,
  produced runtime session `01a03e49-c603-7361-be2c-c23c29e6f5ba`, and reported
  `done — launcher smoke ok`. It exposed the pending-confirm reporting window.
- Second smoke deliberately delayed confirmation while the worker began its
  report. After confirmation, runtime session
  `01a03e4d-e577-7631-b334-0367af0fcc5e` reported
  `done — launcher smoke two ok` and `SMOKE_TWO_OK` without the earlier error.
- Both worker panes were closed and both smoke instructions were wrapped into
  `~/.straw-boss/dispatch/archive/` after their terminal status was verified.

## Automated evidence

- Launcher recovery, Claude delayed-session, sessionless Codex identity,
  genuine-failure cleanup, and fast-worker confirmation tests pass.
- Hook command tests pass with an unset `CLAUDE_PLUGIN_ROOT` from the plugin
  directory and with an explicit root from another directory.
- `python3 -m unittest discover -s tests -p 'test_*.py'` — 91 tests passed on
  2026-08-27 after transcript-confirmed prompt delivery.
- Both plugin manifests parse with `jq -e`; `git diff --check` passed.
- A fake Claude viewport regression renders 11 columns and six visible lines;
  the bounded marker is confirmed without retry and a launch receipt is written.
- The article demo retained one coordinator plus database, API, and web workers
  in a maximized four-pane Herdr layout. Each pane exposed 64 viewport rows; all
  15 monorepo contract tests passed after the final worker commit.
