# Deliver the adversarial-review obligation requirements

## Outcome and actors

An independent adversarial review of `cc690f3` confirmed its repair was
substantive — all six findings and all four record corrections closed, each new
test independently reproduced red at `969e0bd` and `7c00f06` — and found one
medium finding plus four low ones inside this spec family's own scope.

The medium finding is a **delivery gap, not a design conflict**.
`choosing-graph` makes adversarial review unconditional for every ordinary
programming change and assigns the action to the worker. Nothing told the
worker: `shipping-task` — the only path such a change takes — never mentioned
it, the generated contract never mentioned it, the brief carries the anchor the
review runs beside rather than the review, and no step anywhere confirmed one
had happened. That is H's original complaint ("a rule takes effect from a file
the skill owning the dispatch never mentions") for the one skill three rounds
never named.

The rest are the same class the previous round closed: a record, a pointer, or a
declaration its own target does not support.

Actors are the user, the main agent, the dispatched worker, the generated
contract both sides read, and the spec records a later reader will treat as
fact.

## In scope

- The delivery path for the adversarial-review obligation: the generated
  contract, `shipping-task`, and the brief; plus an acceptance condition that
  can actually be checked.
- Which routes discharge that obligation, since this repo's own practice
  dispatches the review from the coordinator after the change lands, while the
  rule named only the worker's own route.
- The missing-anchor fallback's scope: it sits inside the contract bullet that
  opens "In `herdr-pane`", while `render_dispatch_contract` takes no mode.
- `dispatching-work` Task 3's Verification, whose opening universal excludes the
  brief element its next clause requires.
- The coordination graph's absence from `docs/roles.md` and from the stance the
  SessionStart hook injects, both of which state the anchor half only.
- The unstated overlap between `orchestrator-worker` and fan-out.
- The release rule's own title, which names one of the two locks it releases.
- `test_no_retired_coordination_alias_is_live_in_the_skills`'s docstring and the
  H row of `2026-08-28-anchor-authority-boundary/verification.md`.
- A forward marker on the one earlier spec bullet a later spec supersedes.

## Out of scope

- `README.zh-TW.md`'s `create-great-harness` row, which drifted at `5c543a4`,
  predates this spec family and belongs to no anchor or graph question.
- Generalizing acceptance to the other three anchors. Their checkpoints live in
  the method the worker and user own; a coordinator verifying those would cross
  the boundary this spec family exists to draw. The adversarial-review
  obligation is stated at coordination level, so it is checked there.
- A structured anchor or review field in the instruction JSON, rejected for the
  same reason as last round.

## Dated records: the rule this change adopts

`2026-08-28-close-rereview-findings/requirements.md` put editing dated records
out of scope and then edited three of them in place. The rule actually in force,
written down here rather than contradicted a third time: **a dated record is
edited in place when it misreports a measurement, misdescribes the tree, or
points at something later superseded — and only then.** Wording that merely
reads as of its own era stays as written.

## User-owned decisions carried into this change

1. Correct directly. No new exception clause, red line, or defensive caveat is
   added to cover a finding.
2. Reality anchor `testing`; the layer inside it is unit-level tests over the
   prose and the generated contract, in `tests/`, each red before its fix. The
   main agent dispatches this change's own adversarial review afterwards.
3. Coordination graph `single-loop`, solo-mode on a clean `main`, committed
   without a push.
