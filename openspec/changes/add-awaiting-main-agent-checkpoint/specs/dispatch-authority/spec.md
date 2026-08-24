## ADDED Requirements

### Requirement: Resolve an awaiting-main-agent checkpoint only through the atomic reply mechanism
The main agent SHALL resolve a dispatched agent's `awaiting-main-agent` checkpoint only by using a mechanism that both delivers its reply to the dispatched agent and clears the checkpoint status in the same action, and SHALL NOT treat the checkpoint as resolved based on reasoning about it that was never delivered to the dispatched agent.

#### Scenario: Main agent receives an awaiting-main-agent event
- **WHEN** the Plan watcher or a provider fast path reports a dispatched agent's `awaiting-main-agent` checkpoint
- **THEN** it SHALL resolve the checkpoint through the atomic reply-and-clear mechanism before considering it addressed, and SHALL NOT treat having formed an answer without sending it as resolving the checkpoint

#### Scenario: Status watcher surfaces an unresolved checkpoint
- **WHEN** the main agent's Plan status watcher surfaces a task still in `awaiting-main-agent`
- **THEN** the main agent SHALL resolve it directly itself through the same atomic reply-and-clear mechanism, rather than deferring it or pointing the user at the dispatched agent's own pane
