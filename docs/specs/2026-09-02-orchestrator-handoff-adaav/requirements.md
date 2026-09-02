# Orchestrator handoff and ADAAV

## Outcome

Keep orchestration lightweight while allowing an approved work scope to move to
a new orchestrator in an independent Herdr tab. The receiving orchestrator owns
that scope through `boss-say`; the original orchestrator stops coordinating it.

Use ADAAV as a compact reasoning order: alignment, continuity, anchor,
implementation, verification. It is not a required five-part response or a
prompt template. Reuse established context and add text only for a real gap,
handoff, decision, or result.

## Confirmed decisions

- Creating another orchestrator always requires explicit user approval because
  every orchestrator is an independent user-facing window.
- The approval question contains one decision and the minimum context needed to
  understand the proposed scope transfer.
- After transfer, the receiving orchestrator exclusively coordinates the
  transferred scope. The original orchestrator may continue only with separate
  work.
- The original orchestrator gives a compact handoff report and does not monitor,
  peek, relay, schedule, or clean up the transferred work afterward.
- After the receiving orchestrator accepts the handoff, the original
  orchestrator closes its own pane automatically when it retains no other work.
  If it retains separate work, it stays open and owns only that scope.
- Continuity carries only the goal and scope, confirmed decisions and canonical
  user terms, current state and evidence, next action, and explicit exclusions.
  It does not copy the complete conversation.
- Ownership changes only after the receiving orchestrator explicitly accepts
  the handoff. If acceptance fails, the original orchestrator retains ownership,
  retries once, then closes the failed new tab and reports the failure compactly.
- ADAAV must simplify prompts. It does not require phase headings, repeated
  context, separate artifacts, or narration for every phase.

## Open decisions

- None currently.
