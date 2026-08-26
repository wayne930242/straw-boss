# Skill sediment pruning requirements

## Outcome and actors

Straw Boss skills must direct agents through concise positive workflows. The
user owns policy choices, the main agent owns coordination, and app-rooted
workers own target-app discovery. A hard guardrail remains only when it is
traceable to an explicit user decision, a provider/mechanical invariant, or a
reproduced failure with evidence.

## In scope

- Remove every `## Red Flags` restatement section from plugin skills.
- Collapse duplicated negative prose into one positive source of truth.
- Replace unconditional `always`/`never` claims with their real applicability
  condition unless the invariant is traceable.
- Move init reconnaissance and shared-resource discovery into app-rooted workers.
- Remove guessed bootstrap defaults from `create-great-harness`.
- Narrow the stale-base repair to tasks whose base can actually move.
- Reconcile batch, single-app routing, investigation, and diagnosis language.
- Correct peeking mechanics to the current instruction, receipt, and status
  schemas.
- Replace tests that require a negative sentence with tests for the positive
  contract.

## Out of scope

- Removing runtime validation, permission limits, session fingerprints, or
  durable status safeguards that have executable coverage.
- Changing the provider-profile/advisor launch behavior delivered in 0.18.8.
- Inventing new app conventions, default hooks, lifecycle policy, or structured
  configuration merely to replace deleted prose.

## Scenarios

1. A skill already states a workflow step and verification criterion; no Red
   Flag repeats the opposite mistake afterward.
2. Init needs app-specific configuration evidence; it dispatches bounded
   reconnaissance rooted in that app and integrates its evidence references.
3. A bootstrap survey finds no project-specific guard or skill system; it writes
   only evidence-grounded `CLAUDE.md` content and adds no speculative hook/rule.
4. Parallel tasks share a moving base; the relevant tasks refresh that base
   before push. A task with no moving-base risk receives no generic rebase rule.
5. A worker needs a port or shared DB; it discovers the target configuration in
   its app and claims only the shared resource it actually uses.
6. Peeking a Plan task resolves its canonical dispatch instruction, reads
   `repo_root` there, reads the agent name from the launch receipt, and treats the
   Plan status as status evidence only.

## Confirmed decisions

- Negative prompts create sediment and are removed when positive steps already
  express the target behavior.
- An incident may justify a guardrail but not a wider population than the
  incident's causal conditions.
- Absence of traceable evidence cannot justify a universal project convention.
- User confirmation on 2026-08-26 authorizes repeated correction rounds until
  these audit findings are resolved.

## Open questions

None.
