# Close the final review findings verification

## Finding disposition

Every finding from the independent adversarial review of `eb52d4c`.

| # | Finding | Disposition |
|---|---|---|
| 中 1 | `choosing-graph`'s two named acceptance points are not a closed set — a direct `boss-say` "close out `<task>`" passthrough reaches `dispatching-work`'s Wrap-up branch with no disposition, and a `work-on`-produced plan left ambiguous whether `shipping-task` Task 6 runs once per task or once for the whole plan | The Wrap-up branch dispositions the review itself, guarded so it never re-runs `shipping-task` Task 6 or `boss-say` Task 7's own work. `choosing-graph` names all three acceptance points. `shipping-task` Task 6 states its per-task frequency for a `work-on`-produced plan explicitly |
| 中低 2 | `docs/roles.md` states a dispatched agent states its own coordination graph for its own task, but no surface a worker is required to read ever carried that instruction | New standing contract bullet, mirroring the existing anchor-naming bullet's own pattern; points to `choosing-graph` for the criterion rather than restating it. `CONTEXT.md`'s glossary entry brought to the same shape as its `Reality anchor` neighbor |
| 低 3 | `boss-say` Task 7 dispositioned the review against a commit reference it never confirmed | Inserts the same confirm-then-discharge order `shipping-task` Task 6 already uses: confirm the item's own completed reference from its terminal report, then discharge against that confirmed reference |
| 低 4 | The contract's review-route list offered "a coworker" to a writable coworker (already forbidden from coordinating another coworker by the bullet before it) and to a headless `claude-p` worker (`bringing-coworker` requires a live Herdr tab it doesn't have) | The route list is conditional on `coworker_context`, already known to `render_dispatch_contract`: a top-level dispatch's contract offers "bringing-coworker from an interactive Herdr tab," a coworker's own contract offers only "a fresh-context subagent." Neither string names a transport |

## Acceptance evidence

| Requirement | Evidence |
|---|---|
| A direct close-out dispositions its own review, without duplicating `shipping-task`/`boss-say`'s work | `test_a_directly_closed_out_dispatch_dispositions_its_own_review` requires the guard clause, the confirm-then-discharge step, and the Verification line in `dispatching-work` |
| A `work-on`-produced plan's disposition frequency is stated | `test_shipping_task_dispositions_a_work_on_plans_review_per_task` requires the per-task sentence and its Verification-line counterpart in `shipping-task` |
| The enumeration itself names all three acceptance points | `test_every_path_that_lands_a_change_checks_the_review` requires `choosing-graph`'s updated sentence and `boss-say`'s statement and confirm-then-disposition Verification line |
| `boss-say` confirms before it dispositions | `test_boss_say_confirms_the_items_own_reference_before_dispositioning_it` requires the confirm-the-reference clause |
| The worker's own coordination-graph obligation reaches the contract | `test_the_workers_own_coordination_graph_obligation_reaches_the_contract` renders the real contract and requires the new bullet |
| The glossary entry states both halves | `test_the_coordination_graph_glossary_entry_states_the_workers_half_too` requires the updated `CONTEXT.md` sentence |
| The review route list is narrowed to what each reader can do | `test_the_review_route_offers_bringing_coworker_only_where_it_can_run` renders the contract for a top-level dispatch and for both coworker variants, and requires `bringing-coworker` on the first and no mention of "coworker" on either of the other two |

## Do the new tests actually fail on the defect?

Six new tests plus one retargeted test were written first, run against the
unmodified tree at `eb52d4c`:

```text
python3 -m unittest tests.test_skill_instruction_quality   # before any fix
Ran 48 tests — FAILED (failures=7)

test_a_directly_closed_out_dispatch_dispositions_its_own_review
test_boss_say_confirms_the_items_own_reference_before_dispositioning_it
test_every_path_that_lands_a_change_checks_the_review
test_shipping_task_dispositions_a_work_on_plans_review_per_task
test_the_coordination_graph_glossary_entry_states_the_workers_half_too
test_the_review_route_offers_bringing_coworker_only_where_it_can_run
test_the_workers_own_coordination_graph_obligation_reaches_the_contract
```

Each failure was an assertion on the defect itself, not an import or parse
error:

```text
test_the_review_route_offers_bringing_coworker_only_where_it_can_run
  AssertionError: 'bringing-coworker' not found in "An ordinary programming
  change carries ... a fresh-context subagent, or a coworker ..."
test_the_workers_own_coordination_graph_obligation_reaches_the_contract
  AssertionError: 'State your own coordination graph for this task before you
  start, through choosing-graph' not found in "..." (the rendered contract)
test_the_coordination_graph_glossary_entry_states_the_workers_half_too
  AssertionError: 'The coordinator states it before it dispatches; a
  dispatched agent states its own for its own task' not found in "... The
  coordinator states it. ..."
test_shipping_task_dispositions_a_work_on_plans_review_per_task
  AssertionError: 'For a work-on-produced plan (Task 1), this task runs once
  per plan task ...' not found in "..." (`shipping-task/SKILL.md`)
```

## Existing tests this change moved

- `test_every_path_that_lands_a_change_checks_the_review` retargets its
  `choosing-graph` and `boss-say` assertions to the new three-point enumeration
  and confirm-then-disposition wording. Every assertion it had is kept, in
  strengthened form (the `choosing-graph` assertion still requires both
  original routes, plus the third; the `boss-say` Verification assertion still
  requires "discharged ... and dispositioned, not assumed," plus the new
  completion-reference clause) — none weakened.

## Commands

```text
python3 -m unittest discover -s tests
141 tests passed

python3 -m compileall -q scripts tests
passed

git diff --check
passed
```
