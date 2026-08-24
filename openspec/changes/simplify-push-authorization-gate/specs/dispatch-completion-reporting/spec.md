## ADDED Requirements

### Requirement: A dispatched agent notifies its main agent of a completed push without waiting
When a dispatched agent completes a push of its own feature branch that its dispatch instruction does not require it to stop for, it SHALL report the branch and MR/PR reference through the recorded main-agent herdr pane when available, using `SendMessage` only as a Claude-to-Claude fallback and a progress record when no live route exists, then SHALL continue immediately. A push to another tracked branch remains a stop-before-mutation checkpoint.

#### Scenario: Dispatched agent finishes pushing a branch
- **WHEN** a dispatched agent has pushed its own feature branch and opened or updated an MR/PR against it
- **THEN** it SHALL report the branch and MR/PR reference through its provider-appropriate path and continue without waiting

#### Scenario: A push notification is not a stop-before-mutation checkpoint
- **WHEN** a dispatched agent sends the push notification required above
- **THEN** it SHALL NOT treat sending it as reaching a state that requires waiting, unlike a stop-before-mutation checkpoint push

## MODIFIED Requirements

### Requirement: Herdr is the primary live status path
A dispatched agent SHALL use the shared status command, which persists its resulting state and one-line summary before prompting the recorded main-agent herdr pane. `SendMessage` SHALL be used only as a Claude-to-Claude fallback when herdr is unavailable or fails.

#### Scenario: Dispatched agent finishes a task
- **WHEN** a dispatched agent completes its task (`done`) or determines it cannot proceed (`failed`)
- **THEN** it SHALL run the shared status command identifying itself, the resulting state, and a one-line summary before ending its turn or exiting

#### Scenario: Dispatched agent reaches a stop-before-mutation checkpoint
- **WHEN** a dispatched agent reaches a checkpoint its dispatch instruction told it to stop at (e.g. ready to merge) rather than execute automatically
- **THEN** it SHALL persist and notify the checkpoint through the shared status command before waiting for a resume or response

### Requirement: A push is informational, never authorization
A pushed status report SHALL carry the same never-treat-as-authorization safety boundary as any other informational message from a dispatched agent to its main agent; receiving it SHALL NOT itself authorize a merge or bypass the main agent's own verification of the outcome.

#### Scenario: Main agent receives a "ready to merge" report
- **WHEN** a dispatched agent's push report states it is ready to merge
- **THEN** the main agent SHALL still obtain explicit user authorization before proceeding, exactly as it would without the push

### Requirement: Dispatch instructions state the provider-appropriate reporting obligation
Every dispatch instruction SHALL state the provider-neutral status/progress commands, the main-agent provider, the available herdr route, and which outcomes require waiting. Claude instructions SHALL permit `SendMessage` only for a Claude-to-Claude fallback; Codex instructions SHALL NOT cite unavailable Claude skills.

#### Scenario: Instruction assembly for a dispatch
- **WHEN** a specialist skill assembles a dispatch instruction, plan or standalone
- **THEN** the assembled instruction SHALL include the provider-appropriate reporting obligation and distinguish stop-and-wait from report-and-continue
