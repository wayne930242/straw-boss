# Dispatched-agent lifecycle and transport verification

## Automated evidence

- `python3 -m unittest discover -s tests -v`: 32 tests passed.
- `python3 -m compileall -q scripts tests`: passed.
- `openspec validate --all --strict`: 7/7 items passed.
- `claude plugin validate .`: marketplace validation passed.
- `git diff --check`: passed.
- Direct execution of the registered Stop hook with an unrelated session id:
  exited zero with no output.

Focused integration tests prove:

- contract creation and SHA-256 binding happen during `dispatch-task.py write`;
- Claude receives `--append-system-prompt-file` and Codex receives
  `developer_instructions` before the first task prompt;
- `confirm` refuses a missing or mismatched launch receipt;
- both transport directions resolve from instruction path and refuse a reused
  pane whose live session differs;
- durable status exists before live notification is attempted;
- a dispatched Claude Stop is blocked without a checkpoint/terminal report and
  allowed after a valid report;
- Claude SessionStart repeats the matching worker contract on resume instead of
  applying the orchestrator stance;
- control messages preserve exact slash commands while retaining session
  validation;
- delivery ledgers store content-free proof (digest and length), not a second
  copy of message content;
- wrap-up archives contract, receipt, status, progress, and delivery artifacts;
- active skills expose no provider-native fallback or raw endpoint lookup.

## Architecture redundancy review

Removed:

- `get-main-agent.py`, which exposed raw addressing and forced callers to choose
  a channel;
- `main_agent_send_message_peer` and provider mailbox fallback branches;
- independent herdr subprocess/session resolution in status, launch, and reply
  paths;
- repeated dispatch JSON/path/status helpers now owned by `dispatch_state.py`;
- repeated raw main-agent identity in shared-resource locks, replaced by the
  dispatch instruction path;
- duplicated workflow prose in task prompts, replaced by one generated
  contract;
- substantial routing sediment in dispatch/notification references, replaced
  by short pointers to the script-owned seam.

Intentionally retained:

- `report-task-status.py`: owns durable write-before-notify semantics;
- `reply-to-worker.py`: owns checkpoint validation, transcript confirmation,
  and resolution metadata;
- `watch-plan-status.py`: durable recovery and dependency scheduling, not a
  second live transport;
- provider-specific launch injection inside one launch adapter;
- main-agent self-compact as a self-addressed control, not agent-to-agent
  coordination.

The codebase graph was consulted first, but its refreshed repository index
excluded `scripts/`; post-change script topology was therefore verified with
focused tests plus definition/contradiction scans. The final scan found one
`run_herdr` implementation, one endpoint resolver, and one message sender in
`dispatch_transport.py`.

## Compatibility notes

- Existing instruction files remain readable. An older interactive dispatch
  without a main-session fingerprint can still write durable status, but live
  notification fails closed instead of risking delivery to a wrong pane.
- Historical 2026-08-24 Plan transport specs are marked superseded rather than
  rewritten; they remain evidence for the earlier behavior.
- Headless dispatches have no live reverse channel. Their generated contract is
  still injected at launch, and durable status plus process/watcher observation
  remains the recovery path.

## Delivery state

Implemented and verified in the working tree on 2026-08-25. No commit, push,
version bump, local plugin installation, or release was performed.
