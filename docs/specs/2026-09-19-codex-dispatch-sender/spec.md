Status: approved
Approved at: 2026-09-19
Approved from: User-started dispatched task n7; the task delegates fix selection and pre-authorizes push and install.

# Observable contract

1. Codex sender validation compares the calling shell's thread id with the live worker session before writing status or sending/recording a message, including legacy instructions with null session ids.
2. A mismatched, missing, or unavailable thread identity leaves existing status and delivery records unchanged. The real worker continues to report; main-agent cancellation retains its existing identity check.
3. New Codex workers receive the contract in their opening task message, keeping dispatch instructions out of the config cloned by memory consolidation.
4. Both instruction-path and plan/task status addressing use the same ownership check for live dispatches, including instructions storing `plan_id`.
5. Existing installed 0.30.3 contracts resolve the installed fix through their version-neutral launcher. Their existing prompts remain in memory until a new session starts.

Standards: follow [AGENTS.md](../../../AGENTS.md), preserve provider behavior outside Codex, use English source and documentation, and report tests, review, commit, push and installation separately. This is cooperative process isolation, not a security boundary against processes deliberately forging environment variables or directly editing user-owned files.

Reality anchor: first run regressions red at the status/message and launch boundaries, then run `uv run --with pytest pytest -q tests`, followed by fresh-context diff review before shipping. Verify the live sender with a read-only check; use temporary fixtures for rejected writes.
