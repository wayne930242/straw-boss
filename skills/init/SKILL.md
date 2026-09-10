---
name: init
description: Use to configure managed apps and work routes, sync their instruction summaries, or check dispatch readiness.
---

## Read existing configuration

Resolve the git root and use the [shared read handler](references/apps-config-schema.md#shared-read-handler). Reuse confirmed app and routing choices. An existing configuration is the base for requested changes; an unchanged app needs only missing information checked. Follow the schema's legacy migration rules when the old path is the source.

## Resolve apps and missing fields

Identify candidates from manifests and common app directories, then resolve any ambiguous target with the user. For bounded discovery, load the target app's instructions and inspect it directly. Use a separate app-rooted workroom when ownership or continuity warrants it; follow [dispatch readiness](#check-dispatch-readiness) before launching one through [dispatching-work](../dispatching-work/SKILL.md).

Propose fields from app evidence using the [field reference](references/apps-config-schema.md#field-reference). Required fields are `name`, `dir`, and `match`. Optional fields need evidence or user-supplied policy: redirects, lifecycle restrictions, provider defaults, git workflow skills, local files, and cross-app skill pointers. `localFiles` lists existing untracked, gitignored files; use `optional: true` only when the app remains operable without the file, and identify sensitive entries.

Ask only about choices the request and evidence leave unresolved. Write the resolved `.straw-boss/apps.json`, read it back through the shared handler, and preserve unrelated fields.

## Configure work routes

Read existing routing sections in root `AGENTS.md` and `CLAUDE.md`. Reuse an agreed section; resolve conflicting values with the user. Configure routes when requested or when dispatch needs an unresolved setup.

For a new or changed route, recommend a complete setup from local provider configuration and the user's model preferences; consult current official guidance when local evidence is insufficient. Each route records:

`<work description> → worker: kind=<kind>, profile=<profile|default>, model=<model|default>, effort=<effort|default>; advisor=<model|none>`

Confirm unresolved choices for that route as a whole. A Claude route may use a supported native advisor; Codex records `advisor=none`. Put confirmed routes between `<!-- straw-boss:agent-routing:start/end -->` markers in both root instruction files. Preserve text outside the markers.

## Check dispatch readiness

Before any dispatch, check the CLI/service (`command -v herdr`, `herdr status`), current pane and provider identity, and provider integration (`herdr integration status`). A missing Claude integration can be installed with `herdr integration install claude` under the user's authorization for its global hook/settings change. Codex readiness uses its live provider session and terminal identity.

Create `dispatch/` and `dispatch/archive/` under `Path.home() / ".straw-boss"` when needed. Report unmet dependencies separately from configuration completion; local configuration and instruction sync can finish without Herdr. Every launch rechecks readiness through `dispatching-work`.

## Fill missing instructions

Check whether each relevant app has `AGENTS.md` and `CLAUDE.md`, reusing a current inventory. Existing `.agents/skills/`, `.claude/skills/`, rules, and hooks also supply app-owned instructions.

Offer [create-great-harness](../create-great-harness/SKILL.md) for missing files while preserving existing instructions. Carry an existing bootstrap authorization; ask only for an unrequested addition. Use the same inline/workroom choice as discovery. Source changes follow the target's `leveraging-tasks` workflow when available.

## Sync root summaries

Finish any repo-root bootstrap before editing the same files here. Create missing root instruction files with a project heading. Update only the managed-apps block in each file:

```markdown
<!-- straw-boss:apps:start -->
## Managed apps (straw-boss)

api — apps/api
web — apps/web

Full config: `.straw-boss/apps.json`.
<!-- straw-boss:apps:end -->
```

Read back both files: app summaries must match the configuration, routing blocks must match the confirmed routes, and surrounding content must be preserved.

**Complete when:** requested configuration and instruction sync are verified, dispatch readiness is reported, and any bootstrap is complete or has a recorded next event.
