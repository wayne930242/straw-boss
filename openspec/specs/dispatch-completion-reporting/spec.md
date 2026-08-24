# dispatch-completion-reporting Specification

## Purpose
Defines provider-neutral durable state and provider-specific fast notifications for dispatched agents, so mixed Claude/Codex Plans can schedule dependency waves reliably while standalone tasks retain a readable trail.
## Requirements
### Requirement: Plan status transitions are provider-neutral scheduling events
Every Plan dispatched agent SHALL persist each checkpoint or terminal outcome through the same status interface. The main agent SHALL run a watcher that emits every valid file-content transition and use those events to recompute ready waves, regardless of agent kind.

#### Scenario: Codex prerequisite completes
- **WHEN** a Codex Plan task persists `done`
- **THEN** the watcher SHALL emit that transition and the main agent SHALL recompute and dispatch newly ready dependents

#### Scenario: Checkpoint later becomes terminal
- **WHEN** one task's existing status file changes from an `awaiting-*` checkpoint to `done` or `failed`
- **THEN** the watcher SHALL emit the later transition instead of deduplicating by filename

#### Scenario: Main-agent watcher restarts
- **WHEN** a new watcher starts while Plan status files already exist
- **THEN** it SHALL emit every current valid status once so scheduling state can be recovered

### Requirement: Claude SendMessage remains an additive fast path
A Claude dispatched agent SHALL continue to send the `SendMessage` report defined by `notifying-main-agent`. That push SHALL reduce notification latency but SHALL NOT be required for Plan dependency correctness. A Codex dispatch SHALL NOT be required to provide a Claude mailbox identity.

#### Scenario: Claude Plan task finishes
- **WHEN** a Claude Plan task persists `done` or `failed`
- **THEN** it SHALL also send its Claude `SendMessage` report, while the status watcher independently emits the scheduling event

### Requirement: A Claude herdr-pane nudge may supplement its SendMessage push
A Claude dispatched agent reachable via a herdr pane MAY additionally send a faster nudge into its main agent's own pane, but this SHALL NOT substitute for that Claude agent's `SendMessage` fast path. Codex uses its provider-neutral status record and may use the herdr pane directly when interactive.

#### Scenario: Dispatched agent has both herdr and SendMessage reachability
- **WHEN** a Claude dispatched agent's instruction gives it both a main-agent herdr pane id and a `SendMessage` peer name
- **THEN** it SHALL still send the `SendMessage` push required above, whether or not it also sends a herdr nudge

### Requirement: Dispatch instructions state the provider-appropriate reporting obligation
Every dispatch instruction SHALL include the exact provider-neutral progress/status commands. A Claude instruction SHALL additionally require `notifying-main-agent`; a Codex instruction SHALL be self-contained and SHALL NOT point to unavailable Claude skills or `SendMessage`.

#### Scenario: Instruction assembly for a dispatch
- **WHEN** a specialist skill assembles a dispatch instruction, plan or standalone
- **THEN** the assembled instruction SHALL include the status/progress commands and only the notification mechanisms available to its resolved agent kind

### Requirement: Plan active detection is authoritative; standalone active detection remains a fallback
The main agent SHALL keep the Plan status watcher active for scheduling. For a standalone dispatch, process/pane observation remains the fallback when the provider's notification path is absent or quiet.

#### Scenario: Claude push arrives before its matching watcher event
- **WHEN** a Claude Plan task's fast push arrives first
- **THEN** the main agent MAY react immediately but SHALL still keep the watcher as the authoritative recoverable scheduling path

#### Scenario: Standalone dispatch goes quiet
- **WHEN** a standalone dispatch has no provider notification within a reasonable wait
- **THEN** the main agent SHALL inspect its durable status plus process or pane state rather than infer completion from silence

### Requirement: A push is informational, never authorization
A pushed status report SHALL carry the same never-treat-as-authorization safety boundary as any other informational message from a dispatched agent to its main agent; receiving it SHALL NOT itself authorize a push/merge or bypass the main agent's own verification of the outcome.

#### Scenario: Main agent receives a "ready to push" report
- **WHEN** a dispatched agent's push report states it is ready to push or merge
- **THEN** the main agent SHALL still obtain explicit user authorization before proceeding, exactly as it would without the push

### Requirement: Main-agent reachability is recorded as a structured, script-readable field
A dispatch instruction SHALL record the main-agent reachability available to its provider: herdr pane id when applicable, and a `SendMessage` peer name only when the agent kind supports that channel.

#### Scenario: Dispatch instruction is written
- **WHEN** a dispatch instruction is written, for `herdr-pane` or `claude-p` mode
- **THEN** it SHALL record the applicable reachability fields without requiring a Claude peer name from Codex

#### Scenario: Claude dispatched agent prepares to send its push
- **WHEN** a Claude dispatched agent is about to send the `SendMessage` push required by this capability
- **THEN** it SHALL obtain its main agent's current reachability info by reading the structured fields back via a script, not solely from its own recollection of its dispatch prompt's prose

### Requirement: A dispatched agent can log progress at any point during its work
A dispatched agent SHALL be able to append a timestamped, free-text progress note to a durable, per-dispatch log at any point during its work, independent of and in addition to the terminal-state/checkpoint push — appending a progress note SHALL NOT itself send a `SendMessage` push.

#### Scenario: Dispatched agent logs an intermediate progress note
- **WHEN** a dispatched agent wants to record what it is currently doing, before reaching any terminal state or checkpoint
- **THEN** it SHALL be able to append a note to its own dispatch's progress log without that action alone notifying the main agent

#### Scenario: A peek reads the progress log first
- **WHEN** the main agent or the user wants to know what a dispatched agent is currently doing
- **THEN** the check SHALL read the dispatched agent's progress log first, and SHALL only read the dispatched agent's live pane or transcript when the log does not answer the question

### Requirement: A standalone dispatch records a real terminal state, not only a push
A standalone dispatch SHALL have a durable, readable terminal-state record — parallel to a plan task's status file — that a pull-based check can read, independent of provider notification availability.

#### Scenario: Standalone dispatch reaches done or failed
- **WHEN** a standalone dispatched agent reaches `done` or `failed`
- **THEN** it SHALL record that terminal state in a durable, readable form and use any additional notification mechanism available to its provider
