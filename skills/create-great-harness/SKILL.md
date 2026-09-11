---
name: create-great-harness
description: Use when an app is missing AGENTS.md or CLAUDE.md, or the user asks for a minimal agent system.
---

## Establish the scope

Build or fill the app's `AGENTS.md` and `CLAUDE.md`.
Reuse authorization from the user request or dispatch instruction.
Optional hooks and authoring rules require concrete project evidence and authorization covering that addition.

Carry source changes through the target's `leveraging-tasks` workflow when available, retaining the confirmed scope and findings.

## Read and write

Read existing instructions, manifests, lockfiles, and relevant project documentation.
Retain project-specific conventions and boundaries a fresh agent cannot readily derive from those sources.
A near-empty instruction file is valid for an idiomatic app.

Create missing files from the applicable shared instructions; preserve existing text within the authorized scope.
Use relevant sections such as Role, Scope, and Standards, omitting empty sections.
Keep each instruction actionable and grounded in project evidence.

## Optional guard or authoring rule

For an authorized guard, inspect the provider's existing hook configuration and resolve a conflicting event/matcher before writing.
Test both a blocking input and an allowed input using the provider's actual hook payload and decision contract.
Merge the configuration, read it back, and report any activation or restart requirement.
Use the installed provider's current contract for paths and hook behavior.

For an authorized skill-authoring rule, verify the provider's current skill and rule specifications.
Scope the rule to its skill directory, record the source and date, and preserve existing rules.
If the specification cannot be verified, report that unresolved artifact.

## Report

Check both instruction files and any optional artifacts against the confirmed scope.
Report the written files, their line counts, and outstanding recommendations or activation steps.
A dispatched worker reports its outcome through [notifying-main-agent](../notifying-main-agent/SKILL.md#report-status).

**Complete when:** scoped artifacts are verified and the result distinguishes completed writes from remaining work.
