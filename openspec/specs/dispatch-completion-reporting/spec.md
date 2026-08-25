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

### Requirement: Herdr is the primary live notification path
Whenever a dispatch instruction records a main-agent herdr pane, the shared status command SHALL persist the checkpoint or terminal outcome first and then notify that pane with `herdr agent prompt`, regardless of either endpoint's provider. A failed prompt SHALL NOT roll back the durable state.

#### Scenario: Mixed-provider Plan task finishes
- **WHEN** a Claude or Codex Plan task reports `done` or `failed` to a Claude or Codex main agent whose pane is recorded
- **THEN** the command SHALL write the status before prompting that pane, while the status watcher independently emits the scheduling event

#### Scenario: Main agent cancels a dispatch
- **WHEN** the main agent writes `cancelled` for a dispatch it is ending
- **THEN** the command SHALL persist cancellation without prompting the main agent's own pane

### Requirement: SendMessage is Claude-to-Claude fallback only
`SendMessage` SHALL be offered only when both the dispatched agent and main agent are Claude. It MAY serve as fallback when no herdr pane is recorded or a herdr prompt fails, but SHALL NOT be recorded, required, or attempted when either endpoint is Codex.

#### Scenario: Claude worker reports to Codex main agent
- **WHEN** a Claude worker is dispatched by a Codex main agent
- **THEN** its instruction SHALL use the recorded herdr pane and SHALL NOT carry or request a `SendMessage` peer

#### Scenario: Claude-to-Claude herdr succeeds
- **WHEN** a Claude worker's status command successfully prompts its Claude main agent's recorded pane
- **THEN** it SHALL NOT also require `SendMessage`

### Requirement: Generated dispatch contracts state the provider-appropriate reporting obligation
Every generated dispatch contract SHALL include the exact provider-neutral progress/status commands and only the reachability supported by the sender/receiver pair. Task-specific prose SHALL NOT duplicate these mechanics. A Claude or Codex worker uses the same instruction-keyed contract and SHALL NOT need provider-native routing details in its task brief.

#### Scenario: Contract assembly for a dispatch
- **WHEN** a specialist skill dispatches a plan or standalone task
- **THEN** the generated contract SHALL include the status/progress commands while the task-specific prose remains focused on the requested outcome and verified context

### Requirement: Plan active detection is authoritative; standalone active detection remains a fallback
The main agent SHALL keep the Plan status watcher active for scheduling. For a standalone dispatch, process/pane observation remains the fallback when the provider's notification path is absent or quiet.

#### Scenario: Herdr notification arrives before its matching watcher event
- **WHEN** a Plan task's herdr notification arrives first
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
A dispatch instruction SHALL record `main_agent_kind` independently from `agent_kind`, the main-agent herdr pane id when applicable, and a `SendMessage` peer name only for a Claude-to-Claude pair.

#### Scenario: Dispatch instruction is written
- **WHEN** a dispatch instruction is written, for `herdr-pane` or `claude-p` mode
- **THEN** it SHALL record both endpoint providers and the applicable reachability fields without requiring or accepting a Claude peer name across providers

#### Scenario: Dispatched agent prepares to report
- **WHEN** a dispatched agent is about to report or a Claude worker needs its fallback
- **THEN** it SHALL obtain the main-agent provider and preferred channel by reading the structured fields back via a script, not solely from prompt recollection

### Requirement: A dispatched agent can log progress at any point during its work
A dispatched agent SHALL be able to append a timestamped, free-text progress note to a durable, per-dispatch log at any point during its work, independent of and in addition to terminal-state/checkpoint reporting — appending a progress note SHALL NOT itself send a live notification.

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
