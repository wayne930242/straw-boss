## MODIFIED Requirements

### Requirement: Authorization escalation is unaffected
The authorization gate on merge, and on a push landing outside a dispatched agent's own feature branch, SHALL remain unchanged by this escalation order and SHALL NOT be satisfied by a second opinion or an informational reply. Pushing the agent's own feature branch needs no authorization to begin with, so this requirement does not apply to it.

#### Scenario: Dispatched agent needs merge or other-branch-push authorization
- **WHEN** a dispatched agent reaches a merge checkpoint, or a checkpoint for a push landing outside its own feature branch
- **THEN** it SHALL follow the existing authorization flow unchanged, regardless of any second opinion or informational exchange that occurred earlier in the task
