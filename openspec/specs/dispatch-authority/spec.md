## Purpose

Defines what the main agent may do to work it has already dispatched — inform, redirect, cancel — and the boundary of its authority to act on discoveries without asking the user first.
## Requirements
### Requirement: Inform without interrupting
The main agent SHALL be able to send a dispatched agent information about a discovery without interrupting the dispatched agent's current turn.

#### Scenario: Main agent informs a running dispatched agent
- **WHEN** the main agent has something informational to tell a dispatched agent that is still working
- **THEN** the main agent SHALL deliver it in a way that queues behind the current turn rather than interrupting it, and this action SHALL NOT change the dispatched agent's terminal status

### Requirement: Redirect a dispatched agent mid-task
The main agent SHALL be able to interrupt and redirect a dispatched agent whose current task is still correct but needs adjustment.

#### Scenario: Main agent redirects a running dispatched agent
- **WHEN** the main agent determines a running dispatched agent's task needs to change while the task itself remains valid
- **THEN** the main agent SHALL interrupt the dispatched agent's current turn and issue the corrected instruction

### Requirement: Cancel a wrongly-dispatched task
The main agent SHALL be able to end a dispatched task outright when it judges the dispatch itself, not the dispatched agent's execution, was wrong, without waiting for user authorization.

#### Scenario: Main agent cancels a task it dispatched by mistake
- **WHEN** the main agent determines a dispatched task should never have been dispatched as specified
- **THEN** the main agent SHALL end that task and record its status as `cancelled`, distinct from `done` and `failed`

#### Scenario: Cancel a task running as a headless background process
- **WHEN** the main agent cancels a dispatched task running as a headless one-shot background process with no live pane to interrupt
- **THEN** the main agent SHALL stop the backgrounded process directly and record its status as `cancelled`, discarding whatever the task was mid-way through

### Requirement: Autonomy boundary for spec adjustments
The main agent SHALL be permitted to adjust an item's spec or add new work, without asking the user first, only for items not yet dispatched or for in-flight dispatch instructions of already-running tasks, and SHALL always state such an adjustment rather than make it silently.

#### Scenario: Main agent adjusts an undispatched item
- **WHEN** the main agent discovers, before dispatching an item, that its spec should change
- **THEN** the main agent SHALL adjust it on its own judgment and state that it did so, without asking the user first

#### Scenario: Adjustment diverges substantially from the user's direction
- **WHEN** a discovered adjustment would diverge substantially from what the user asked for
- **THEN** the main agent SHALL defer to the user rather than deciding on its own

### Requirement: Authorization gates remain absolute
The main agent's inform/redirect/cancel authority SHALL NOT extend to authorizing a push or merge, or to bypassing `forbidDirectCommit`, regardless of scope.

#### Scenario: Autonomous adjustment reaches a push/merge checkpoint
- **WHEN** a task under the main agent's autonomous adjustment reaches a push or merge checkpoint
- **THEN** the main agent SHALL still obtain explicit user authorization before proceeding, exactly as for any other task

### Requirement: Dispatched-agent failure reporting is unaffected
A dispatched agent's own failure SHALL continue to report through the provider-neutral status command, which persists state before sending the primary herdr notification when a main-agent pane is recorded. `SendMessage` MAY be used only as a Claude-to-Claude fallback. The decision to redispatch a genuinely failed task SHALL remain the user's, unaffected by the main agent's inform/redirect/cancel authority.

#### Scenario: A dispatched task fails on its own
- **WHEN** a dispatched agent's own execution fails, and it was not cancelled by the main agent
- **THEN** it SHALL persist `failed` and notify through the recorded herdr pane when available, using `SendMessage` only for a valid Claude-to-Claude fallback, and the main agent SHALL ask the user before redispatching it
