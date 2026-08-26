# Clear dispatch instruction specification

## Observable contract

- Every task-specific dispatch brief starts from the requested outcome and
  includes enough verified context for a worker entering the repository cold.
- Relevant context includes confirmed acceptance criteria, the reason for the
  work, domain facts the main agent already knows, and exact source or artifact
  references that save rediscovery.
- The worker and user choose specification, design, implementation, and
  verification method in the dispatched session.
- Generic workflow, reporting commands, provider routing, checkpoint mechanics,
  tracker policy, and defensive reminders are omitted from task prose when the
  generated contract or target-project instructions already supply them.
- A task-specific boundary is included only when it is verified and materially
  changes the requested result, such as an exact cross-task artifact or a
  user-confirmed non-goal.
- The same rules apply to standalone, batch, and Plan task descriptions.

## Generated lifecycle contract

The generated contract remains concise and supplies the universal mechanics:

- canonical instruction path;
- progress and coordination commands;
- `awaiting-user-input` for a decision only the user can make;
- `awaiting-main-agent` for coordination or action owned by the main agent;
- `awaiting-authorization` only when an existing project or task rule requires
  approval for the next action;
- terminal `done` or `failed` reporting before stopping.

The contract does not invent task scope or implementation restrictions.

## Compatibility and non-goals

- Instruction JSON schema and launcher/provider behavior remain compatible.
- Existing dispatch artifacts are unchanged and no in-flight task is redirected.
- This change does not add a word limit, forbidden-word linter, or automatic
  prompt rewriting; those would recreate the same over-constraint problem.
- Existing authority rules remain authoritative. This change only removes their
  unnecessary duplication from task-specific prose.

## Applied standards and precedent

- `AGENTS.md` instructions supplied for this run: read before write, do only the
  requested change, and place automation or specialized behavior in its owning
  mechanism rather than prose.
- `scripts/dispatch_state.py:render_dispatch_contract`: existing universal
  lifecycle seam.
- `docs/specs/2026-08-25-dispatched-agent-lifecycle-transport/`: task authors
  supply task semantics while the generated contract supplies lifecycle prose.
- `skills/work-on/SKILL.md`: the dispatched instruction carries user intent and
  lets the target app's own development route govern execution.

## Correctness strategy

- Extend the lifecycle integration test so generated contracts expose the three
  distinct checkpoint statuses.
- Add a focused source-contract test for `shipping-task` and Plan mechanics:
  they require outcome/context-first briefs and reject the former exhaustive
  boilerplate checklist.
- Run the focused tests, full unittest suite, Python compilation, and strict
  OpenSpec validation.

## Human appropriateness

No separate final checkpoint is required. The user already supplied the
appropriateness criterion: clear instructions and sufficient context without
interfering extras.

## User confirmation

Confirmed on 2026-08-25 in this conversation.
