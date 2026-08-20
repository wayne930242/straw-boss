## Purpose

Defines how a dispatched agent — plan or standalone — notifies its main agent it reached `done`, `failed`, or a checkpoint the main agent must act on, and how it makes its own progress visible along the way, so the main agent has a guaranteed-delivery primary signal and a readable trail instead of depending solely on writing state somewhere and hoping something is watching it, or joining the dispatched agent's own live pane to find out what it's doing.

## ADDED Requirements

### Requirement: SendMessage push as the primary completion signal
A dispatched agent SHALL send its main agent a `SendMessage` push — identifying itself, the resulting state, and a one-line summary — the moment it reaches `done`, `failed`, or a checkpoint requiring the main agent to act (e.g. ready to push/merge), regardless of whether it is a plan task or a standalone dispatch.

#### Scenario: Dispatched agent finishes a task
- **WHEN** a dispatched agent completes its task (`done`) or determines it cannot proceed (`failed`)
- **THEN** it SHALL send a `SendMessage` push identifying itself, the resulting state, and a one-line summary, to its main agent, before ending its turn (`herdr-pane`) or before exiting (`claude-p`)

#### Scenario: Dispatched agent reaches a stop-before-mutation checkpoint
- **WHEN** a dispatched agent reaches a checkpoint its dispatch instruction told it to stop at (e.g. ready to push/merge) rather than execute automatically
- **THEN** it SHALL send a `SendMessage` push naming the checkpoint and what it is ready to do, to its main agent, before waiting for a resume or response

### Requirement: State persistence is not itself notification
A dispatch's own state-persistence mechanism (a plan task's status file) SHALL continue to record the dispatch's outcome for programmatic consumers (`plan.json` sync, wave computation, status reads), but SHALL NOT be treated as having notified the main agent on its own — the `SendMessage` push is what satisfies the notification requirement, independent of whether the state was also persisted.

#### Scenario: Plan task writes its status file
- **WHEN** a plan task writes `done`/`failed`/a checkpoint to its status file
- **THEN** it SHALL also send the `SendMessage` push required above; the status-file write alone SHALL NOT be treated as having notified the main agent

### Requirement: A herdr-pane nudge may supplement, never substitute for, the SendMessage push
A dispatched agent reachable via a herdr pane MAY additionally send a faster nudge into its main agent's own pane, but this SHALL NOT substitute for the `SendMessage` push, since a pane-queued message has no delivery guarantee the way a `SendMessage` send to a live, correctly-addressed peer does.

#### Scenario: Dispatched agent has both herdr and SendMessage reachability
- **WHEN** a dispatched agent's dispatch instruction gives it both a main-agent herdr pane id and a `SendMessage` peer name
- **THEN** it SHALL still send the `SendMessage` push required above, whether or not it also sends a herdr nudge

### Requirement: Dispatch instructions state the reporting obligation
Every dispatch instruction — plan or standalone — SHALL state, alongside the main-agent reachability info it already provides, that the dispatched agent must send a `SendMessage` push on reaching `done`, `failed`, or a checkpoint.

#### Scenario: Instruction assembly for a dispatch
- **WHEN** a specialist skill assembles a dispatch instruction, plan or standalone
- **THEN** the assembled instruction SHALL include the reporting-obligation statement, not just the reachability info alone

### Requirement: Active detection is a bounded fallback, not the primary mechanism
The main agent SHALL treat its own active detection of a dispatched agent's state (a plan task's `Monitor` polling loop; a standalone dispatch's `agent wait`/`agent read`, or a `claude-p` process/background-notification signal) as a fallback used only once a still-open dispatch has gone quiet longer than a stated threshold without a push having arrived — not as the first or sole way it learns of an outcome.

#### Scenario: Push arrives before the fallback threshold
- **WHEN** a dispatched agent's `SendMessage` push arrives before its main agent's fallback threshold is reached
- **THEN** the main agent SHALL act on the pushed report and SHALL NOT need to have separately polled for it

#### Scenario: No push arrives within the fallback threshold
- **WHEN** a still-open dispatch has gone quiet longer than the stated threshold with no push received
- **THEN** the main agent SHALL fall back to actively checking the dispatch's own state (its status file, its live pane state, or its process/background-notification signal) to determine whether it actually finished

### Requirement: A push is informational, never authorization
A pushed status report SHALL carry the same never-treat-as-authorization safety boundary as any other informational message from a dispatched agent to its main agent; receiving it SHALL NOT itself authorize a push/merge or bypass the main agent's own verification of the outcome.

#### Scenario: Main agent receives a "ready to push" report
- **WHEN** a dispatched agent's push report states it is ready to push or merge
- **THEN** the main agent SHALL still obtain explicit user authorization before proceeding, exactly as it would without the push

### Requirement: Main-agent reachability is recorded as a structured, script-readable field
A dispatch instruction SHALL record its main agent's current reachability info (its herdr pane id, when applicable, and its `SendMessage` peer name) as structured fields, readable back by a script, not only as prose stated once in the dispatched agent's own prompt.

#### Scenario: Dispatch instruction is written
- **WHEN** a dispatch instruction is written, for `herdr-pane` or `claude-p` mode
- **THEN** it SHALL record the main agent's reachability info as structured fields, resolved at the same time the equivalent prose in the prompt is resolved

#### Scenario: Dispatched agent prepares to send its push
- **WHEN** a dispatched agent is about to send the `SendMessage` push required by this capability
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
A standalone dispatch SHALL have a durable, readable terminal-state record — parallel to a plan task's status file — that a pull-based check can read, independent of whether its `SendMessage` push was received.

#### Scenario: Standalone dispatch reaches done or failed
- **WHEN** a standalone dispatched agent reaches `done` or `failed`
- **THEN** it SHALL record that terminal state in a durable, readable form in addition to sending the `SendMessage` push
