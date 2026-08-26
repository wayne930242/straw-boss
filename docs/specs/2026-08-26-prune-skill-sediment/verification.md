# Verification

Date: 2026-08-26

## Scope

Reviewed the active Straw Boss skills and their directly referenced mechanics
for speculative defensive prose, duplicated negative rules, ungrounded global
assumptions, cross-skill contradictions, and artifact-schema drift.

## Exercised flows

- App discovery and init reconnaissance ownership.
- Minimal harness artifact selection.
- Dispatch brief ownership and evidence-bearing research routes.
- Batch and single-app routing boundaries.
- Moving-base refresh and shared-resource coordination conditions.
- Peek instruction, launch-receipt, and status artifact resolution.
- Post-merge primary-checkout synchronization.

## Findings and resolution

- Removed all ten `Red Flags` sections and replaced required behavior at its
  positive source step.
- Moved target-app reconnaissance from the coordinator to rooted workers.
- Made optional harness artifacts, moving-base refresh, shared-resource locks,
  and primary-checkout sync conditional on observable scope or state.
- Corrected the peek schema to use `<app>--<slug>.json`, `repo_root`, the launch
  receipt's agent identity, and non-routing status metadata.
- Added regression contracts for these boundaries and for quoted hypothetical
  defense bullets.

No release-blocking finding remains in the declared scope.

## Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` — 75 tests passed.
- Both plugin manifests parse with `jq -e`.
- `git diff --check` passed.
- Static scans found no `## Red Flags` section and no quoted hypothetical
  defense bullet under `skills/`.
