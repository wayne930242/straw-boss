## Purpose

Lets a dispatched agent run under an agent CLI other than `claude` (starting with `codex`), chosen per app or per dispatch, while keeping every existing permission-mirroring and traceability guarantee intact regardless of which CLI actually runs.

## Requirements

### Requirement: Default agent kind
Dispatching an agent SHALL default to the `claude` CLI when no other agent kind is configured for the target app and none is given for the dispatch, preserving existing behavior for every app that predates this capability.

#### Scenario: No agent kind configured anywhere
- **WHEN** a dispatch is prepared for an app with no agent kind set in its configuration and no explicit override given for the dispatch
- **THEN** the dispatched agent SHALL run under the `claude` CLI

### Requirement: Per-app agent kind default
The managed-apps configuration SHALL support declaring a non-default agent kind for a given app, which SHALL be used for every dispatch into that app unless a specific dispatch overrides it.

#### Scenario: App configured with a non-default kind
- **WHEN** an app's configuration declares an agent kind other than `claude`
- **THEN** a dispatch into that app SHALL run under the configured kind unless that dispatch explicitly overrides it

### Requirement: Per-dispatch agent kind override
The main agent SHALL be able to specify an agent kind for one dispatch that differs from the target app's configured default, without editing the app's configuration.

#### Scenario: One-off override
- **WHEN** the main agent dispatches into an app while explicitly specifying an agent kind different from that app's configured default
- **THEN** that one dispatch SHALL run under the explicitly given kind, and the app's own configured default SHALL remain unchanged for future dispatches

### Requirement: Permission level is never exceeded regardless of agent kind
Every dispatched agent, regardless of its agent kind, SHALL be launched with a permission/execution-restriction level that is no more permissive than the main agent's own current permission mode.

#### Scenario: Dispatching a non-claude agent under a restricted main agent
- **WHEN** the main agent's own session is running under a restricted permission mode and it dispatches an agent whose kind is not `claude`
- **THEN** the dispatched agent SHALL be launched with that agent kind's own equivalent restriction, never with fewer restrictions than the main agent's own mode

### Requirement: Non-claude dispatch is restricted to standalone tasks
A dispatch whose resolved agent kind is not `claude` SHALL be a standalone dispatch only. It SHALL NOT be used for a plan task or a batch item.

#### Scenario: A plan or batch task resolves to a non-claude app default
- **WHEN** a plan task or batch item targets an app whose configured agent kind is not `claude`
- **THEN** that task SHALL be dispatched under `claude` instead, and the main agent SHALL state that it overrode the app's configured default and why, rather than silently dispatching under the app's default or silently dispatching under `claude` without explanation

### Requirement: Unresolvable agent kind is refused, not substituted
When an app's configuration or a dispatch's explicit override names an agent kind that has no known launch/permission mapping, the dispatch SHALL be refused before any process is launched.

#### Scenario: Unsupported kind requested
- **WHEN** a dispatch's resolved agent kind has no launch/permission mapping available
- **THEN** the dispatch SHALL be refused before any process starts, and the main agent SHALL report the unsupported kind rather than silently substituting a different one

### Requirement: Setup offers to configure more than one additional agent kind
Project setup SHALL ask, once per project rather than once per app, whether to enable one or more agent kinds beyond `claude`, and SHALL allow configuring more than one additional kind — a second and a third are both allowed, not just a single non-`claude` toggle.

#### Scenario: User enables a second agent kind, then a third
- **WHEN** the user opts into a non-`claude` agent kind during project setup
- **THEN** setup SHALL ask what kind of work should route to that kind and what model/reasoning-effort it should run at, and SHALL allow configuring a further additional agent kind the same way, without limiting the project to a single non-`claude` kind

### Requirement: Recommended model/effort is grounded in existing preference, confirmed before recording
When recommending a model or reasoning-effort for a configured agent kind, setup SHALL consult whatever local preference already exists for that agent kind before proposing one, and SHALL have the user confirm or override the recommendation before it is recorded anywhere.

#### Scenario: A local preference already exists
- **WHEN** the user's environment already has a recorded preference for the agent kind being configured
- **THEN** the recommendation SHALL be grounded in that existing preference rather than an invented default

#### Scenario: No local preference exists
- **WHEN** no local preference exists for the agent kind being configured
- **THEN** setup SHALL look up a current recommendation before proposing one, rather than guessing

#### Scenario: Recommendation is presented, not silently applied
- **WHEN** setup has arrived at a model/effort recommendation for a configured agent kind
- **THEN** it SHALL be presented to the user for confirmation or override before being recorded, never written unconfirmed

### Requirement: Agent-kind routing policy is recorded as project-wide prose, not per-app structured config
The decision of which kind of work should route to which agent kind, model, and effort SHALL be recorded as a prose policy in the project's root CLAUDE.md, not as a structured per-app rule table.

#### Scenario: Routing policy is written
- **WHEN** setup records a routing decision for an additional agent kind
- **THEN** it SHALL write that decision into the project's root CLAUDE.md rather than into the per-app configuration file

### Requirement: Dispatch record carries the resolved agent kind
Every dispatch instruction SHALL record which agent kind it actually ran under, so a later status check, wrap-up, or report can distinguish dispatches by agent kind.

#### Scenario: Listing outstanding dispatches
- **WHEN** the main agent lists outstanding dispatch instructions
- **THEN** each instruction's recorded agent kind SHALL be available to distinguish it from a dispatch running under a different kind
