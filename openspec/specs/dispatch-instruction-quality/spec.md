# dispatch-instruction-quality Specification

## Purpose

Defines how Straw Boss writes task-specific dispatch briefs so workers receive
clear instructions and sufficient context without speculative or generic
restrictions that distort their judgment.

## Requirements

### Requirement: Task briefs are outcome and context first

Every dispatched task brief SHALL lead with a clear requested outcome and SHALL
include sufficient verified context for a worker entering the target app cold.

#### Scenario: Worker receives a feature task

- **WHEN** a main agent assembles a standalone or Plan task brief
- **THEN** the brief SHALL state the outcome, confirmed acceptance context, and relevant source or artifact references before any task-specific constraint

### Requirement: Speculation is context, not a boundary

A possible implementation, suspected scope, or unresolved interpretation SHALL
be presented as a lead to investigate and SHALL NOT be phrased as a prohibition
or fixed implementation boundary.

#### Scenario: Main agent knows a likely implementation path

- **WHEN** the main agent includes that path in a task brief
- **THEN** the brief SHALL identify it as a lead and leave the worker free to revise it after reading the target project

### Requirement: Generic lifecycle mechanics stay out of task prose

Task-specific prose SHALL NOT repeat progress commands, provider routing,
checkpoint mechanics, tracker policy, or defensive reminders already supplied
by the generated contract, the calling skill, or the target project's own
instructions.

#### Scenario: A task needs normal lifecycle reporting

- **WHEN** a task is dispatched
- **THEN** the generated contract SHALL supply lifecycle mechanics and the task brief SHALL remain focused on what the worker must deliver

### Requirement: Material task-specific constraints remain allowed

Any constraint included in a dispatch brief SHALL be verified, task-specific,
and material to the acceptable result or required input.

#### Scenario: Plan task consumes a prerequisite artifact

- **WHEN** a task cannot proceed correctly without an earlier task's artifact
- **THEN** its exact artifact path SHALL appear in the brief as required context
