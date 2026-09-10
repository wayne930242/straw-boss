---
name: work-on
description: Use to resolve which of the project's managed apps a request belongs to.
---

## Resolve the app

Resolve the git root, then use the [shared read handler](../init/references/apps-config-schema.md#shared-read-handler). Exit 0 returns the configuration; exit 3 uses the implicit-app branch below; exit 1 requires correcting the reported configuration error.

- **No configuration:** use the repo root as an implicit app when it contains one codebase. Derive its name from the manifest or directory name. With several plausible apps, ask which directory the request targets.
- **One active app:** use it unless the request is explicitly outside that app.
- **Several apps:** match the request against every entry's `name` and `match`. Return each app touched; clarify an ambiguous match.
- **Legacy entry:** apply `redirectTo` for new work and surface its `note`. An audit of existing legacy code stays in that checkout; a user-confirmed compatibility fix can also stay there.
- **External or unmanaged work:** return that classification to the caller.

## Return

Return the app names, absolute directories, config source, and applicable `crossAppSkills` pointers. App ownership alone establishes no dependency order. The caller uses [boss-say](../boss-say/SKILL.md#plan-and-schedule) for work needing a plan; this skill only resolves targets.

**Complete when:** the caller has unambiguous targets or a specific unresolved routing question.
