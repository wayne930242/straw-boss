## MODIFIED Requirements

### Requirement: Plan status transitions are provider-neutral scheduling events
Every Plan dispatched agent SHALL persist each checkpoint or terminal outcome through the same status interface. The main agent SHALL run a watcher that emits every valid file-content transition and use those events to recompute ready waves, regardless of agent kind.

#### Scenario: Dispatched agent reaches a checkpoint requiring the main agent's own action
- **WHEN** a dispatched agent cannot continue until its main agent takes an action within its own judgment or dispatch authority, rather than a human answering a question
- **THEN** it SHALL persist `awaiting-main-agent`, naming what action is needed, before the shared status command prompts the recorded main-agent herdr pane; only a Claude-to-Claude pair MAY fall back to `SendMessage`
