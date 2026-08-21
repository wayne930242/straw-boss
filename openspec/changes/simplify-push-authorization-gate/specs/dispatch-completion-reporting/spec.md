## ADDED Requirements

### Requirement: A dispatched agent notifies its main agent of a completed push without waiting
When a dispatched agent completes a push of its own feature branch that its dispatch instruction does not require it to stop for (opening or updating an MR/PR against that branch, or a further push to it), it SHALL send a `SendMessage` push identifying the branch and MR/PR reference, and SHALL continue its work immediately rather than waiting for a resume or response — distinct from a stop-before-mutation checkpoint push, which does wait. A push that lands on or modifies a tracked branch other than the agent's own feature branch is not covered by this requirement and remains a stop-before-mutation checkpoint.

#### Scenario: Dispatched agent finishes pushing a branch
- **WHEN** a dispatched agent has pushed its own feature branch and opened or updated an MR/PR against it
- **THEN** it SHALL send a `SendMessage` push naming the branch and MR/PR reference to its main agent, and SHALL continue working without waiting for any reply

#### Scenario: A push notification is not a stop-before-mutation checkpoint
- **WHEN** a dispatched agent sends the push notification required above
- **THEN** it SHALL NOT treat sending it as reaching a state that requires waiting, unlike a stop-before-mutation checkpoint push

## MODIFIED Requirements

### Requirement: SendMessage push as the primary completion signal
A dispatched agent SHALL send its main agent a `SendMessage` push — identifying itself, the resulting state, and a one-line summary — the moment it reaches `done`, `failed`, or a checkpoint requiring the main agent to act (e.g. ready to merge), regardless of whether it is a plan task or a standalone dispatch.

#### Scenario: Dispatched agent finishes a task
- **WHEN** a dispatched agent completes its task (`done`) or determines it cannot proceed (`failed`)
- **THEN** it SHALL send a `SendMessage` push identifying itself, the resulting state, and a one-line summary, to its main agent, before ending its turn (`herdr-pane`) or before exiting (`claude-p`)

#### Scenario: Dispatched agent reaches a stop-before-mutation checkpoint
- **WHEN** a dispatched agent reaches a checkpoint its dispatch instruction told it to stop at (e.g. ready to merge) rather than execute automatically
- **THEN** it SHALL send a `SendMessage` push naming the checkpoint and what it is ready to do, to its main agent, before waiting for a resume or response

### Requirement: A push is informational, never authorization
A pushed status report SHALL carry the same never-treat-as-authorization safety boundary as any other informational message from a dispatched agent to its main agent; receiving it SHALL NOT itself authorize a merge or bypass the main agent's own verification of the outcome.

#### Scenario: Main agent receives a "ready to merge" report
- **WHEN** a dispatched agent's push report states it is ready to merge
- **THEN** the main agent SHALL still obtain explicit user authorization before proceeding, exactly as it would without the push

### Requirement: Dispatch instructions state the reporting obligation
Every dispatch instruction — plan or standalone — SHALL state, alongside the main-agent reachability info it already provides, that the dispatched agent must send a `SendMessage` push on reaching `done`, `failed`, a checkpoint, or a completed push notification for its own feature branch, and SHALL make clear which of these require waiting for a response and which do not — including that a push to any other tracked branch remains a stop-before-mutation checkpoint, not a fire-and-continue notification.

#### Scenario: Instruction assembly for a dispatch
- **WHEN** a specialist skill assembles a dispatch instruction, plan or standalone
- **THEN** the assembled instruction SHALL include the reporting-obligation statement, not just the reachability info alone, and SHALL distinguish a stop-and-wait checkpoint from a report-and-continue notification where both apply
