# dispatched-agent-escalation Specification

## Purpose
Defines the order a dispatched agent follows when it cannot resolve something on its own, so a solvable technical difficulty gets a second opinion before it ever reaches the user, while missing-context questions and judgment calls still go straight to whoever can actually answer them.
## Requirements
### Requirement: Escalation order for a stuck dispatched agent
A dispatched agent that cannot resolve something on its own SHALL try, in order: an informational question to its main agent when the answer is context the main agent already has; a stronger second opinion, if one is available to it, when it is stuck on genuine technical difficulty rather than missing context or a judgment call reserved for the user; escalation to the user for a judgment call, or once a second opinion does not resolve a genuine technical difficulty.

#### Scenario: Dispatched agent is missing context its main agent has
- **WHEN** a dispatched agent needs a fact its main agent already knows (e.g. another task's status, which apps are in scope)
- **THEN** it SHALL ask via its informational-question channel, not escalate to the user or seek a second opinion first

#### Scenario: Dispatched agent is stuck on genuine technical difficulty
- **WHEN** a dispatched agent is stuck on a technical problem that is not missing context and not a judgment call reserved for the user
- **THEN** it SHALL consult a stronger second opinion first, if one is available to it, before escalating to the user

#### Scenario: Dispatched agent faces a judgment call
- **WHEN** a dispatched agent's difficulty is a judgment call reserved for the user (a values, architecture, or direction decision)
- **THEN** it SHALL escalate directly to the user without first seeking a second opinion, since a second opinion cannot make that call on the user's behalf

### Requirement: Second-opinion availability is not assumed
A dispatched agent SHALL NOT assume a specific second-opinion tool is available to it; the escalation order SHALL degrade to going straight to the user when no such tool is available.

#### Scenario: No second-opinion tool available
- **WHEN** a dispatched agent stuck on genuine technical difficulty has no stronger second-opinion tool available to it
- **THEN** it SHALL escalate directly to the user rather than stall looking for one

### Requirement: Authorization escalation is unaffected
The push/merge authorization gate SHALL remain unchanged by this escalation order and SHALL NOT be satisfied by a second opinion or an informational reply.

#### Scenario: Dispatched agent needs push/merge authorization
- **WHEN** a dispatched agent reaches a push/merge checkpoint
- **THEN** it SHALL follow the existing authorization flow unchanged, regardless of any second opinion or informational exchange that occurred earlier in the task

