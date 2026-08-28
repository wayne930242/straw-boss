# Close the final review findings requirements

## Outcome and actors

An independent adversarial review of `eb52d4c` confirmed the previous three
rounds' findings stayed closed — none reopened — and found one medium finding,
one medium-low finding, and two low ones inside this spec family's own scope,
all four introduced or left unaddressed by `eb52d4c` itself and not present as
findings in any earlier round.

The medium finding is the same **enumeration** defect class the previous round
closed for the worker/coordinator split, recurring one level up: `choosing-graph`
named two acceptance points for the adversarial-review obligation while a third,
real path — `boss-say`'s own "close out `<task>`" passthrough to
`dispatching-work`'s Wrap-up branch — reaches neither, and a `work-on`-produced
plan left it ambiguous whether `shipping-task` Task 6 disciplines once per task
or once for the whole plan.

The medium-low finding is a delivery gap of the same shape H originally named,
recurring for a different obligation: `docs/roles.md` states a dispatched agent
states its own coordination graph for its own task, but nothing a worker is
required to read ever carried that instruction — every live pointer to
`choosing-graph` for this purpose sat on coordinator-side task text.

The two low findings are a missing precondition (`boss-say` Task 7 disposed a
reference it never confirmed) and an unnarrowed route list (the contract named
"a coworker" as a review route for two readers who cannot actually take it).

Actors are the user, the main agent, the dispatched worker, a coworker, the
generated contract every worker reads, and the spec records a later reader will
treat as fact.

## In scope

- The acceptance-point enumeration for the adversarial-review obligation: a
  direct `dispatching-work` close-out and a `work-on`-produced plan, made
  explicit and testable alongside the two routes `eb52d4c` already named.
- The worker-facing delivery surface for the coordination-graph obligation
  `docs/roles.md` already states.
- `boss-say` Task 7's disposition precondition: confirming the item's own
  completion reference before dispositioning the review against it.
- The generated contract's review-route list, narrowed to what each reader can
  actually do: a writable coworker cannot nest another coworker (its own
  contract bullet already forbids it), and a headless `claude-p` worker has no
  Herdr tab for `bringing-coworker` to use.

## Out of scope

- `README.zh-TW.md`'s `create-great-harness` row — stale since `5c543a4`,
  predates this spec family, and the user has already ruled it out of scope
  twice.
- The launcher trust-prompt bug and the `awaiting-user-input` pane-archiving
  feature the review's live-evidence gathering touched — neither is a
  coordination-graph, reality-anchor, or adversarial-review contract defect.
- The read-only-anchor half of `inspecting-app`/`investigating-app`'s
  Verification (no disposition step for that anchor's own findings) — this is
  the same H shape carried forward from `969e0bd`, not a new inconsistency
  `eb52d4c` introduced, and the user's dispatch did not name it.
- Redesigning how a `work-on`-produced plan's wave dispatch runs — only the
  disposition responsibility at its end.

## Dated records: the rule already in force

`2026-08-28-deliver-adversarial-review-obligation/requirements.md` recorded the
rule this change follows too: a dated record is edited in place only when it
misreports a measurement, misdescribes the tree, or points at something later
superseded. No record from an earlier round meets that bar here, so none is
edited.

## User-owned decisions carried into this change

1. Correct directly. No new exception clause, red line, or defensive caveat is
   added to cover a finding.
2. Reality anchor `testing`; unit tests over the prose and the generated
   contract, in `tests/`, each red before its fix. The main agent dispatches
   this change's own adversarial review afterwards.
3. Coordination graph `single-loop`, solo-mode on a clean `main`, committed
   without a push.
