## MODIFIED Requirements

### Requirement: Authorization gates remain absolute
The main agent's inform/redirect/cancel authority SHALL NOT extend to authorizing a merge, or to bypassing `forbidDirectCommit`, regardless of scope. Pushing the task's own feature branch (opening or updating an MR/PR against it, or a further push to that same branch) is not an authorization gate — it requires no authorization to begin with, so there is nothing for this autonomy to bypass. A push that lands on or modifies any other tracked branch — the target/base branch directly, a monorepo root's submodule pointer-bump, a version-bump/release-tag push an app-owned git-workflow skill's remaining steps might perform against a protected/base branch — remains an authorization gate, unaffected by this requirement.

#### Scenario: Autonomous adjustment reaches a merge checkpoint
- **WHEN** a task under the main agent's autonomous adjustment reaches a merge checkpoint
- **THEN** the main agent SHALL still obtain explicit user authorization before proceeding, exactly as for any other task

#### Scenario: A push targets a branch other than the task's own feature branch
- **WHEN** a dispatched task's mutation is a push that lands on or modifies a tracked branch other than its own feature branch (e.g. a monorepo-root submodule pointer-bump, or a release/version-bump push to a protected branch)
- **THEN** the main agent SHALL still obtain explicit user authorization before that push, exactly as it would for a merge
