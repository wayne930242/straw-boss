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

### Requirement: Agent-kind resolution applies to standalone, batch, and Plan tasks
A dispatch SHALL preserve its resolved supported agent kind regardless of whether it is standalone, a batch item, or a dependency-tracked Plan task. Plan state reporting and dependency scheduling SHALL use provider-neutral status interfaces rather than forcing a non-Claude task to Claude.

#### Scenario: A Plan task resolves to Codex
- **WHEN** a Plan task targets an app whose configured or explicitly selected agent kind is `codex`
- **THEN** that task SHALL dispatch under Codex, record `agent_kind: codex`, and participate in the same status/ready-wave protocol as a Claude task

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

### Requirement: Work routes carry a complete provider setup
Project setup SHALL let each work-type route select an agent kind, optional provider-native profile, optional model, optional reasoning effort, and, for Claude Code only, an optional native advisor model. The complete route SHALL be confirmed before it is recorded.

#### Scenario: Claude programming route uses a native advisor
- **WHEN** the user confirms a programming route with a Claude worker model and a Claude advisor model
- **THEN** the route SHALL record both models as one Claude Code worker setup and SHALL NOT describe the advisor as a coworker or separate dispatch

#### Scenario: Codex route declines an advisor
- **WHEN** the user confirms a Codex work route
- **THEN** setup SHALL make clear that Codex has no native advisor and SHALL NOT configure or emulate one

### Requirement: Dispatch instruction records the resolved provider setup
Every dispatch instruction SHALL record its resolved optional provider profile, model, effort, and Claude-only advisor model so execution and later reporting use the same confirmed setup.

#### Scenario: Complete Claude route is dispatched
- **WHEN** a Claude route resolves to a named agent profile, worker model, effort, and advisor model
- **THEN** the instruction SHALL record all four values together with `agent_kind: claude`

#### Scenario: Older instruction omits new fields
- **WHEN** an existing instruction has no provider-profile or advisor-model field
- **THEN** launch and status handling SHALL treat those fields as unset and preserve prior behavior

### Requirement: Provider launch applies instruction-owned setup
The provider launch adapter SHALL translate the recorded provider profile, model, effort, and supported advisor into the selected CLI's native arguments. Raw provider arguments SHALL be refused when they duplicate an option owned by the instruction.

#### Scenario: Claude setup is launched
- **WHEN** a Claude instruction records a provider profile, model, effort, and advisor model
- **THEN** launch SHALL apply them as Claude Code `--agent`, `--model`, `--effort`, and `--advisor` arguments exactly once

#### Scenario: Codex setup is launched
- **WHEN** a Codex instruction records a provider profile, model, and effort
- **THEN** launch SHALL apply them as Codex `--profile`, `--model`, and `model_reasoning_effort` configuration arguments exactly once

#### Scenario: Codex advisor is requested
- **WHEN** instruction creation or launch receives an advisor model for Codex
- **THEN** the dispatch SHALL be refused visibly before starting a worker and SHALL NOT substitute a coworker, subagent, profile, or second dispatch

### Requirement: Dispatch brief preserves worker-owned context discovery
The main agent SHALL dispatch the user requirement, requested outcome, necessary hints and constraints, dependencies, exact supplied artifact references, and verified coordination facts it already knows. It SHALL NOT investigate the target app's implementation, precedent, or tests merely to enrich the brief; that context discovery belongs to the dispatched worker in its own harness.

#### Scenario: Main agent has enough information to route a task
- **WHEN** the target app, requested outcome, constraints, and dependencies are known
- **THEN** the main agent SHALL dispatch without first researching target-app implementation context

#### Scenario: A verified cross-task fact is already available
- **WHEN** the main agent already knows a dependency result or shared-resource constraint relevant to the task
- **THEN** it SHALL include that coordination fact in the brief without expanding it into a target-app investigation

### Requirement: Target-app research is dispatched and evidence-bearing
When coordination or integration requires problem investigation, audit, diagnosis, or current-state research inside a managed app, the main agent SHALL dispatch that work into the app instead of reading across the app root. A bounded investigation MAY use a user-confirmed lower-tier work route, but its question SHALL require an explanatory conclusion and evidence references rather than a yes-or-no existence answer.

#### Scenario: Integration lacks a current-state fact
- **WHEN** integration needs to understand a managed app's current behavior or problem
- **THEN** the main agent SHALL dispatch an investigator rooted in that app and SHALL integrate the returned conclusion and evidence references without loading the app's files itself

#### Scenario: Bounded investigation uses a lower-tier model
- **WHEN** a confirmed work route assigns bounded research to Haiku or a lower-tier Codex model
- **THEN** the dispatch SHALL use that route and SHALL still require the worker to explain the behavior, mechanism, cause, or impact with traceable evidence

#### Scenario: Proposed research question is binary
- **WHEN** a draft investigation asks only whether something exists or is true
- **THEN** the dispatch brief SHALL instead ask for the relevant current behavior and the evidence that establishes the conclusion
