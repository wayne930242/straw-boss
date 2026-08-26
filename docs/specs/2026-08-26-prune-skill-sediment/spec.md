# Skill sediment pruning specification

## Observable contract

- No plugin `SKILL.md` contains a `## Red Flags` section.
- Operational behavior is stated once, positively, beside its completion or
  verification criterion.
- Global modal claims identify one of these sources in nearby prose: user policy,
  provider/runtime constraint, executable schema, or reproduced incident.
- Init reads Straw Boss coordination/config state and directory-level candidate
  metadata only. App content reconnaissance runs in an app-rooted dispatch and
  returns proposed fields plus evidence references.
- `create-great-harness` always writes only evidence-grounded `CLAUDE.md`
  content. A hook or rule is optional and requires a concrete discovered need or
  explicit confirmed scope; there is no generic destructive-hook default,
  automatic skill-writing rule, or arbitrary line-count gate.
- Moving-base refresh applies when parallel work or observed remote advancement
  can make the task stale, not to every Plan/batch task.
- A batch may contain independent items. The normal Plan path dispatches its
  ready wave; the capped batch path deliberately slices it.
- Single-app routing still excludes work explicitly outside the managed app.
- Managed-app investigation/audit/diagnosis dispatches and requests an
  explanatory evidence-backed result using positive language.
- Shared-resource details are discovered by the worker. Locking applies only to
  a resource actually shared across concurrent tasks.
- Peek mechanics use current schema ownership: instruction for
  mode/session/`repo_root`, launch receipt for agent name/pane, status record for
  status/note/refs.

## Compatibility and non-goals

- Public script CLIs and persisted JSON shapes remain unchanged.
- Existing runtime safety checks remain intact.
- This refactor does not claim that every negative word is invalid; error
  messages and irreducible safety boundaries can remain when paired with the
  valid path.
- No new config field or automatic policy is introduced.

## Applied standards and evidence

- Workspace `AGENTS.md`: read before write, do only requested work, verify.
- `writing-great-skills`: single source of truth, pruning, sediment, no-op, and
  positive prompting guidance.
- `docs/roles.md`: main agent owns coordination; worker owns target-app context.
- Audit of commit `67eb72c`: 112 Red Flag bullets across ten skills, schema drift
  in peeking references, and the cross-skill contradictions recorded in
  `requirements.md`.
- Reproduced incidents in `plan-mechanics.md` remain evidence, but their rule is
  narrowed to the incident's moving-base conditions.

## Correctness strategy

- A new static quality test goes red on Red Flag sections, guessed bootstrap
  defaults, coordinator-owned app reconnaissance, stale peek schema, negative
  sentence locks, and the identified contradictions.
- Existing lifecycle integration tests characterize runtime behavior throughout
  the documentation refactor.
- Focused tests, the complete unittest suite, strict OpenSpec validation, skill
  validators, plugin validation, and a final modal/contradiction scan close the
  work.

## Human appropriateness

No later checkpoint is needed. The user explicitly approved the audit's repair
direction and authorized multiple correction rounds on 2026-08-26.
