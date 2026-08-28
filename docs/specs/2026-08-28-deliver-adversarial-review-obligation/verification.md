# Deliver the adversarial-review obligation verification

## Finding disposition

Every finding from the independent adversarial review of `cc690f3`.

| # | Finding | Disposition |
|---|---|---|
| 中 1 | Adversarial review is mandatory for every ordinary programming change, but `shipping-task`, the contract, and the brief never mention it and nothing checks it happened | The obligation becomes a standing contract bullet, because it never varies and a per-dispatch brief would inherit the anchor's own delivery failure. `shipping-task` Task 4 states it and Task 6 discharges it against the confirmed reference and dispositions what it reports. `choosing-graph` names both routes, since this repo dispatches the review from the coordinator as often as the worker runs it |
| 低 2 | The spec bullet a later spec declares superseded carries no marker | Inline forward marker on the bullet, per `docs/qa/`'s precedent for a superseded item rather than a superseded document. The dated-record rule actually in force is written into `requirements.md` instead of being contradicted a third time |
| 低 3 | The missing-anchor fallback sits inside the contract's `In herdr-pane` bullet, and `render_dispatch_contract` takes no mode | The bullet splits: the mode-scoped half ("you and the user choose") stays, the anchor-authority half becomes unconditional and names `awaiting-main-agent` so it stays executable where no reply can arrive |
| 低 4 | Task 3's Verification opens with a universal that excludes the brief element its next clause requires | The universal is scoped to every brief statement *about the work*; the coordination the dispatch fixed is stated as the brief's own element. A fourth source was rejected — it restores the deleted exception under a new name |
| 低 5 | `README.zh-TW.md`'s `create-great-harness` row is stale | Out of scope by the user's decision: it drifted at `5c543a4`, predates this spec family, and belongs to no anchor or graph question |
| 次要 | `orchestrator-worker`/fan-out overlap unadjudicated | Stated as a precedence rule in its own paragraph. The pair tie-break keeps its scope, so `close-rereview-findings/design.md`'s argument against a three-way rule is not reversed — this writes down the boundary that record called "already decided cleanly" |
| 次要 | `docs/roles.md` and the injected stance define the anchor but not the graph | Both now define both |
| 次要 | The release rule's title names one of the two locks it releases | Retitled "Releasing every lock on a wrapped-up instruction"; both pointers moved with it |
| 次要 | The retired-alias docstring says "multi-word phrases" while `topology` is one word | Docstring describes the list it actually scans |
| 次要 | The H row still reads as a cost reduction | Corrected the same way `cc690f3` corrected the same narrative in the sibling `design.md`: the cost is unchanged, its disclosure is what changed |

## Acceptance evidence

| Requirement | Evidence |
|---|---|
| The obligation reaches every worker, and cannot be dropped by a brief | `test_the_adversarial_review_obligation_reaches_every_worker` splits the real `render_dispatch_contract` output into top-level bullets, requires exactly one carrying bullet, requires it to name which dispatches it covers, and requires it to name no transport |
| Both discharge routes are named | `test_both_routes_that_discharge_the_review_are_named` requires the worker's route, the coordinator's route, and the Verification clause covering either |
| The skill carrying ordinary changes states and checks it | `test_the_skill_that_carries_ordinary_changes_states_and_checks_the_review` requires the Task 4 statement, the Task 6 disposition step, and the Task 6 acceptance condition |
| Every path that lands a change checks it | `test_every_path_that_lands_a_change_checks_the_review` requires `choosing-graph` to name both acceptance points and `boss-say` Task 7 to carry the batch item's disposition and its own acceptance condition |
| The fallback holds in every mode and stays executable | `test_the_missing_anchor_fallback_applies_in_every_dispatch_mode` requires it outside the `herdr-pane` bullet, free of transport names, and naming `awaiting-main-agent` |
| The brief's source rule does not exclude the brief's own elements | `test_the_brief_source_rule_governs_what_the_brief_says_about_the_work` requires the scoped universal and the brief's own element; `test_the_deleted_allowed_list_exception_is_actually_gone` keeps its `assertNotIn("reality anchor", ...)` guard on the same sentence, with a locator that no longer empties on a rewording |
| Both coordination decisions are defined where authority is | `test_the_coordination_graph_is_named_where_authority_is_defined` covers `docs/roles.md` and the injected stance |
| The third graph overlap has an answer | `test_orchestrator_worker_is_settled_before_the_two_way_tie_break` extracts the precedence paragraph and requires it not to contain the pair tie-break, so the two rules cannot merge |
| The release rule's title matches what it releases | `test_the_release_rules_own_title_covers_both_locks_it_releases` requires the new title in the paragraph and in both pointers, and the old one nowhere |
| A superseded bullet carries its forward marker | `test_a_superseded_spec_bullet_carries_its_forward_marker` reads the superseding spec's own claim, resolves the directory it names, and requires the marker there — so it fails on the disagreement, not on a missing phrase; `test_the_superseded_marker_is_its_own_block` requires it to stand apart from the claim it retires |

## Do the new tests actually fail on the defect?

All nine were written and run first, against the unmodified tree at `cc690f3`:

```text
python3 -m unittest tests.test_skill_instruction_quality   # before any fix
Ran 40 tests — FAILED (failures=9)

test_a_superseded_spec_bullet_carries_its_forward_marker
test_both_routes_that_discharge_the_review_are_named
test_orchestrator_worker_is_settled_before_the_two_way_tie_break
test_the_adversarial_review_obligation_reaches_every_worker
test_the_brief_source_rule_governs_what_the_brief_says_about_the_work
test_the_coordination_graph_is_named_where_authority_is_defined
test_the_missing_anchor_fallback_applies_in_every_dispatch_mode
test_the_release_rules_own_title_covers_both_locks_it_releases
test_the_skill_that_carries_ordinary_changes_states_and_checks_the_review
```

Each failure was an assertion on the defect itself, not an import or parse
error:

```text
test_the_adversarial_review_obligation_reaches_every_worker
  AssertionError: 0 != 1 : the obligation is one standing contract bullet
test_the_missing_anchor_fallback_applies_in_every_dispatch_mode
  AssertionError: 'In herdr-pane' unexpectedly found in "In herdr-pane, you are
  an independent agent after launch. ..."
test_orchestrator_worker_is_settled_before_the_two_way_tie_break
  AssertionError: 0 != 1 : one precedence rule, stated once
test_a_superseded_spec_bullet_carries_its_forward_marker
  AssertionError: [] == [] : spec.md carries no forward marker
```

Two more tests were written red after the first pass, when review of the
committed change found that `choosing-graph`'s new sentence named
`shipping-task` Task 6 as *the* acceptance point while `boss-say`'s batch items
never reach it, and that the forward marker had landed inside the claim it
retires:

```text
python3 -m unittest tests.test_skill_instruction_quality   # before those fixes
Ran 42 tests — FAILED (failures=2)

test_every_path_that_lands_a_change_checks_the_review
test_the_superseded_marker_is_its_own_block
```

The two narrative corrections — the retired-alias docstring and the H row —
carry no test, for the reason the previous round recorded: a test asserting a
docstring or a disposition-table sentence pins the wording, not the fact.

## Existing tests this change moved

Three assertions were retargeted, none weakened:

- `test_a_dispatch_time_claim_is_released_from_every_terminal_path` and
  `test_the_release_rule_covers_both_locks_its_pointer_claims` locate the
  paragraph by its title, which changed. Both keep every assertion they had.
- `test_the_deleted_allowed_list_exception_is_actually_gone` filtered on the
  exact opening of the universal that this change rewords. Its locator loosened
  to `"brief statement" and "traces to"` so a future rewording cannot silently
  empty the filter; its `assertNotIn("reality anchor", ...)` guard is unchanged.

## Commands

```text
python3 -m unittest discover -s tests
135 tests passed

python3 -m compileall -q scripts tests
passed

git diff --check
passed
```
