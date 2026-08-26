# Clear dispatch instruction requirements

## Outcome and actors

Straw Boss must dispatch work with a clear requested outcome and enough verified
context for the worker to make good decisions. The main agent owns the brief and
the fixed lifecycle contract. The brief carries the user requirement, requested
outcome, and necessary integrated context. The dispatched worker and user own
specification, design, implementation, and verification within the target
project's own instructions.

## In scope

- Define what belongs in task-specific dispatch prose.
- Remove the standing requirement to enumerate workflow, reporting, checkpoint,
  tracker, and mutation boilerplate in every task description.
- Keep provider-neutral communication and lifecycle mechanics in the generated
  dispatch contract.
- Make the generated contract distinguish user-decision, main-agent-action, and
  existing authorization checkpoints without requiring task authors to repeat
  their commands.
- Apply the same instruction-quality rule to standalone and Plan dispatches.

## Out of scope

- Redirecting or changing any currently running dispatch.
- Changing merge, push, deployment, tracker, or shared-resource authority.
- Automatically scoring or rejecting task prose based on length or keywords.
- Replacing the target project's own `AGENTS.md`, `CLAUDE.md`, skills, or rules.

## Scenarios

1. A main agent dispatches a feature request. The task describes the outcome,
   necessary integrated context, and relevant source references; the worker and
   user choose the work definition after inspecting the project.
2. A main agent knows a verified cross-task fact. It supplies the fact and its
   reference as integrated context.
3. A task needs a genuine task-specific constraint. The brief states the
   constraint and why it materially affects the outcome.
4. A worker needs user judgment, main-agent coordination, or authorization
   required by an existing rule. The generated contract supplies the matching
   checkpoint status without duplicating it in the task brief.
5. A Plan task needs an artifact from a prerequisite. Its exact artifact path is
   included because it is required task input, not generic lifecycle prose.

## Confirmed decisions

- Dispatch quality means clear instructions plus sufficient context, not more
  boundaries.
- Prefer positive outcome language and concise integrated context.
- Include a boundary only when it is verified, task-specific, and materially
  changes what the worker may deliver.
- Existing lifecycle mechanics remain mandatory, but live in the generated
  contract or target-project harness instead of being repeated in task prose.
- User confirmation: 2026-08-25, with the instruction to change only the plugin
  and leave the current dispatch alone.

## Open questions

None.
