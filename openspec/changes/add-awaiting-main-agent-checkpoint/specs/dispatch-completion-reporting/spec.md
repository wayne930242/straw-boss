## MODIFIED Requirements

### Requirement: SendMessage push as the primary completion signal
A dispatched agent SHALL send its main agent a `SendMessage` push — identifying itself, the resulting state, and a one-line summary — the moment it reaches `done`, `failed`, or a checkpoint requiring the main agent to act (e.g. ready to push/merge), regardless of whether it is a plan task or a standalone dispatch.

#### Scenario: Dispatched agent finishes a task
- **WHEN** a dispatched agent completes its task (`done`) or determines it cannot proceed (`failed`)
- **THEN** it SHALL send a `SendMessage` push identifying itself, the resulting state, and a one-line summary, to its main agent, before ending its turn (`herdr-pane`) or before exiting (`claude-p`)

#### Scenario: Dispatched agent reaches a stop-before-mutation checkpoint
- **WHEN** a dispatched agent reaches a checkpoint its dispatch instruction told it to stop at (e.g. ready to push/merge) rather than execute automatically
- **THEN** it SHALL send a `SendMessage` push naming the checkpoint and what it is ready to do, to its main agent, before waiting for a resume or response

#### Scenario: Dispatched agent reaches a checkpoint requiring the main agent's own action
- **WHEN** a dispatched agent cannot continue until its main agent takes an action within its own judgment or dispatch authority, rather than a human answering a question
- **THEN** it SHALL send a `SendMessage` push reporting `awaiting-main-agent`, naming what action is needed, to its main agent, before waiting for a resume or response
