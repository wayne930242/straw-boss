# Close the final review findings specification

## Observable behavior

- `choosing-graph` names three acceptance points for the adversarial-review
  obligation, not two: `shipping-task` Task 6 for a task it drives to
  completion, `boss-say` Task 7 for a batch item, and `dispatching-work`'s own
  Wrap-up branch for a dispatch closed out directly by neither.
- `dispatching-work`'s Wrap-up branch dispositions the review itself, guarded
  against re-running work `shipping-task` Task 6 or `boss-say` Task 7 already
  did: it confirms the instruction's own completion reference and the review's
  discharge against that reference only when neither of those two already
  dispositioned it. Its Verification requires that.
- `shipping-task` Task 6 states that for a `work-on`-produced plan, it runs
  once per plan task as each one's own lifecycle completes, not once for the
  whole plan. Its Verification requires that.
- `boss-say` Task 7 confirms the item's own completed merge or commit reference
  from its terminal report before dispositioning the review against that
  confirmed reference — the same two-step order `shipping-task` Task 6 already
  uses. Its Verification requires the reference be confirmed, not just the
  review dispositioned.
- The generated contract's adversarial-review bullet offers "bringing-coworker
  from an interactive Herdr tab" as a route only on a top-level dispatch's own
  contract; a coworker's own contract (`coworker_context` set) offers only "a
  fresh-context subagent," since coworker nesting stops at one level. Neither
  variant names a transport.
- The generated contract carries a new standing bullet: a dispatched agent
  states its own coordination graph for its own task, through `choosing-graph`,
  before it starts.
- `CONTEXT.md`'s `Coordination graph` glossary entry states both halves — the
  coordinator states it before it dispatches, a dispatched agent states its own
  for its own task — matching the neighboring `Reality anchor` entry's shape.

## Records

- None. No earlier dated record misreports a measurement, misdescribes the
  tree, or points at something this change supersedes.
