## MODIFIED Requirements

### Requirement: Dispatched-agent failure reporting is unaffected
A dispatched agent's own failure SHALL continue to report to the main agent through a `SendMessage` push per `dispatch-completion-reporting`, plus its plan status file if it is part of a plan (bookkeeping, not the notification itself), and the decision to redispatch a genuinely failed task SHALL remain the user's, unaffected by the main agent's inform/redirect/cancel authority.

#### Scenario: A dispatched task fails on its own
- **WHEN** a dispatched agent's own execution fails, and it was not cancelled by the main agent
- **THEN** it SHALL send a `SendMessage` push reporting `failed`, additionally writing its plan status file if part of a plan, and the main agent SHALL ask the user before redispatching it
