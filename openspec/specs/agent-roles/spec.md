## Purpose

Defines a single canonical cast of characters (user, main agent, dispatched agent, subagent) and the naming convention that keeps "boss" from ever ambiguously referring to more than one of them across the plugin's skills and identifiers.

## Requirements

### Requirement: Canonical role definitions
The plugin SHALL define user, main agent, dispatched agent, and subagent as a single canonical cast of characters in one reference document, and every skill that uses these terms SHALL reference that document rather than redefining the roles locally.

#### Scenario: A skill uses role terminology
- **WHEN** a skill's `SKILL.md` uses "main agent", "dispatched agent", "user", or "subagent" in its instructions
- **THEN** it SHALL NOT include its own definition of that term and SHALL instead point to the canonical role document

### Requirement: "boss" naming convention
The plugin SHALL treat "boss" as referring only to the user in any identifier — skill name, script name, field name — never to the main agent.

#### Scenario: A new identifier represents the main agent
- **WHEN** a new skill, script, or field is introduced whose purpose is to reach or represent the main agent
- **THEN** its identifier SHALL NOT use "boss" to refer to it

#### Scenario: An existing misnamed identifier is corrected
- **WHEN** an existing identifier uses "boss" to mean the main agent
- **THEN** it SHALL be renamed so no identifier conflates "boss" (the user) with the main agent
