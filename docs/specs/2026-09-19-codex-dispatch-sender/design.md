# Design

Use the existing Herdr session module for one sender invariant: a Codex caller's `CODEX_THREAD_ID` must equal the live `agent_session.value`, in addition to the recorded endpoint checks. The recorded endpoint continues to check provider, terminal and (when present) conversation identity. A null persisted session does not disable caller validation. Missing runtime identity fails before side effects.

Move the Codex contract pointer from provider `developer_instructions` to `task_start_prompt`, the existing adapter used by Antigravity. The startup delivery marker and confirmation path remain unchanged. Claude retains its native system prompt contract. Compared with disabling memory generation, this preserves the user's memory settings and fixes the instruction ownership seam itself.

The plan/task compatibility route must find owners by both legacy `plan` and canonical `plan_id` fields. The public verification surface is the script CLI with a fake Herdr endpoint, plus the launcher boundary. Temporary fixtures keep live task state intact.

## Investigation

- Hypothesis: terminal inheritance is sufficient to pass sender validation. Confirmed by the existing code and red regression using the same pane/terminal with a different caller thread.
- Hypothesis: the contract arrives through shared Codex config. Confirmed in `_LaunchAttempt._provider_args`; upstream phase 2 clones config and leaves `developer_instructions` intact.
- Hypothesis: a Stop hook causes the false report. The shipped Stop guard is Claude-oriented and requires a matching persisted session id; this does not explain a null-id Codex dispatch.
- Hypothesis: querying stored memory-thread metadata can prove caller identity. Consolidation is ephemeral in upstream phase 2, and no matching persisted thread was found locally. Runtime caller/live-thread comparison avoids this dependency.

Upstream source: [phase2.rs](https://github.com/openai/codex/blob/main/codex-rs/memories/write/src/phase2.rs), [exec_env.rs](https://github.com/openai/codex/blob/main/codex-rs/core/src/exec_env.rs). Source supports the inheritance mechanism; the historical ephemeral process transcript is unavailable, so its exact shell environment was not recovered. Local live inspection independently confirms the two runtime identities for the real worker.

## Friction Notes

- Tried: Run the local evidence parser with `python`.
  Found: This shell provides `python3` instead.
  Led by: none
- Tried: Discover production functions through the existing graph.
  Found: Queries returned tests but omitted known production script symbols; direct file inspection was needed.
  Led by: code discovery instructions
- Tried: Read the repository-local model preference profile.
  Found: This checkout has no such skill; the user-level profile supplies the active review model.
  Led by: project routing instructions
- Tried: Fetch the former Codex phase2 source path and an unquoted query URL.
  Found: The source moved to `memories/write/src/phase2.rs`; zsh requires query URLs to be quoted.
  Led by: none

- Tried: Collect the new regression with an imported shared fixture.
  Found: This suite explicitly adds the repository root to `sys.path` before importing `tests`; applying that existing pattern restores collection.
  Led by: none
- Tried: Run the full suite with legacy fake Codex endpoints unchanged.
  Found: The fixtures represented terminal-only identity and inherited the runner's real thread id; they now supply independent, matching fake caller/live conversation ids.
  Led by: task reality anchor
