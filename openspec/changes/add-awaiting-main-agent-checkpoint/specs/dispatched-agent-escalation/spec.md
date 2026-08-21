## MODIFIED Requirements

### Requirement: Escalation order for a stuck dispatched agent
A dispatched agent that cannot resolve something on its own SHALL try, in order: an informational question to its main agent when the answer is context the main agent already has and does not block continued progress while waiting; the `awaiting-main-agent` checkpoint when continuing requires an action only the main agent's own judgment or dispatch authority can take; a stronger second opinion, if one is available to it, when it is stuck on genuine technical difficulty rather than missing context, a main-agent action, or a judgment call reserved for the user; escalation to the user for a judgment call, or once a second opinion does not resolve a genuine technical difficulty.

#### Scenario: Dispatched agent is missing context its main agent has
- **WHEN** a dispatched agent needs a fact its main agent already knows (e.g. another task's status, which apps are in scope) and can keep making progress while waiting for the answer
- **THEN** it SHALL ask via its informational-question channel, not the `awaiting-main-agent` checkpoint, and not escalate to the user or seek a second opinion first

#### Scenario: Dispatched agent is blocked pending an action only the main agent can take
- **WHEN** a dispatched agent cannot continue until its main agent takes an action within its own judgment or dispatch authority (e.g. redispatching a failed dependency, arbitrating a conflict with a peer task, deciding whether to redirect or cancel a related task) rather than merely answering a question
- **THEN** it SHALL report the `awaiting-main-agent` checkpoint rather than use the fire-and-forget informational-question channel or escalate directly to the user

#### Scenario: Dispatched agent is stuck on genuine technical difficulty
- **WHEN** a dispatched agent is stuck on a technical problem that is not missing context, not an action only the main agent can take, and not a judgment call reserved for the user
- **THEN** it SHALL consult a stronger second opinion first, if one is available to it, before escalating to the user

#### Scenario: Dispatched agent faces a judgment call
- **WHEN** a dispatched agent's difficulty is a judgment call reserved for the user (a values, architecture, or direction decision)
- **THEN** it SHALL escalate directly to the user without first seeking a second opinion, since a second opinion cannot make that call on the user's behalf
