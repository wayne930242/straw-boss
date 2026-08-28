# Close the re-review findings verification

## Finding disposition

Every finding from the independent adversarial re-review of `969e0bd`.

| # | Finding | Disposition |
|---|---|---|
| 中 1 | Three records state that Task 3's "or the reality anchor" allowed-list exception was deleted; it is still in the tree | The clause is deleted, which makes all three true at once — including the commit message, which cannot be edited. The following clause now requires the brief to name the anchor it settled on, so the obligation replaces the permission |
| 中 2 | The generated contract declares "the reality anchor this dispatch names" unconditionally, with nothing carrying the anchor | The contract degrades honestly: ask the main agent to name the anchor when the dispatch does not. A structured field was rejected — it relocates the same free-text judgment behind an argument. The fallback keeps the category with the coordinator instead of widening the worker's grant |
| 中 3 | Wrap-up step 3 claims coverage that its target paragraph denies | The paragraph narrows to "the dispatch-time lock" and names the worker-claimed case explicitly. The step also gains an acceptance condition, which it had none of |
| 中 4 | `dispatch shape` is registered as a retired alias while `boss-say` uses it live in another sense | Removed from **coordination graph**'s retired list and registered as its own term. The wider "six of eight aliases unguarded" reading does not hold: `_Avoid_` retires a name for one concept, and a blanket scan would reject "subagent" and "model" on sight |
| 低 5 | `choosing-graph` names three read-only skills; `troubleshooting-app` never mentions an anchor | The rule now names that skill's integration preflight, not the skill, and states that its other branch takes the testing anchor. `troubleshooting-app` names both anchors in its own branch paragraphs |
| 低 6 | `single-loop` and `sub-agent fan-out/fan-in` both fit the same situations, with no adjudication | Tie-break added in the same paragraph as the anchor-check exemption: whether a branch of the work itself runs in a subagent. Replaces the exclusion role D's repair removed |
| r1 | `2026-08-25-clear-dispatch-instructions/spec.md` records the unscoped grant and the reconciliation note omits it | The note in `2026-08-28-anchor-authority-boundary/verification.md` now names both specs. The dated record itself is left as written |
| r2 | `prose_surfaces()`'s non-recursive `docs` scan is undocumented | Documented in the helper's own docstring, with the reason: dated records keep their era's wording |
| r3 | The red-set labels misreport the measurement — "the two vocabulary tests" is one, and the scoping test is missing | Label list corrected to the twelve actually measured, with the lifecycle-vocabulary test named as green and why |
| r4 | `design.md` describes H's rule as now permissive, while `choosing-graph` still makes it mandatory for read-only work | Narrative corrected: the cost is unchanged, its disclosure is what changed |

## Acceptance evidence

| Requirement | Evidence |
|---|---|
| A record of a deletion is true of the tree | `test_the_deleted_allowed_list_exception_is_actually_gone` reads both records' claims and the sentence they describe, so it fails on the disagreement rather than on a missing phrase |
| The contract's anchor reference cannot dangle | `test_the_contract_says_what_to_do_when_a_dispatch_names_no_anchor` builds the real contract through `dispatch_state.render_dispatch_contract` |
| The release rule covers both locks its pointer names | `test_the_release_rule_covers_both_locks_its_pointer_claims` extracts the target paragraph, requires both cases, and requires the new step's acceptance condition |
| No retired coordination phrase is live in the skills | `test_no_retired_coordination_alias_is_live_in_the_skills` parses `CONTEXT.md`, takes the aliases the three coordination entries retire, and scans every instruction line under `skills/`; it also requires **dispatch shape** to keep an entry of its own |
| Every read-only dispatch branch names its anchor | `test_troubleshooting_names_the_anchor_on_both_of_its_branches` covers the skill's two branches and `choosing-graph`'s narrowed rule, and holds the closed-set test's `adversarial-review is its anchor` in place |
| Overlapping graphs have one answer | `test_one_graph_wins_when_single_loop_and_fan_out_both_fit` requires the tie-break and the anchor-check exemption in one paragraph, and requires that paragraph to name the two graphs it adjudicates and not `orchestrator-worker` |

## Do the new tests actually fail on the defect?

The six tests were written and run first, against the unmodified tree at
`969e0bd`:

```text
python3 -m unittest tests.test_skill_instruction_quality   # before any fix
Ran 31 tests — FAILED (failures=6)

test_no_retired_coordination_alias_is_live_in_the_skills
test_one_graph_wins_when_single_loop_and_fan_out_both_fit
test_the_contract_says_what_to_do_when_a_dispatch_names_no_anchor
test_the_deleted_allowed_list_exception_is_actually_gone
test_the_release_rule_covers_both_locks_its_pointer_claims
test_troubleshooting_names_the_anchor_on_both_of_its_branches
```

Each failure was an assertion on the defect itself, not an import or parse
error: the allowed-list test reported "'reality anchor' unexpectedly found in
'**Verification:** every brief statement traces to ...'"; the release test
reported the paragraph's actual opening sentence; the vocabulary test reported
`boss-say`'s four live uses.

The four record corrections carry no test. A misreported measurement and a
narrative that overstates what a rule became are corrected by reading the
measurement and the rule; a test asserting a label matches an old tree's run
would pin the label, not the fact.

## The read-only rule's other surfaces

Narrowing the read-only rule to `troubleshooting-app`'s integration preflight is
not covered by a cross-surface test — the closed-set test compares the four
anchor categories, not the skill list. `docs/architecture.md`, `README.md`, and
`README.zh-TW.md` were read for a repeated three-skill read-only enumeration and
have none: each describes `troubleshooting-app` by its two branches and neither
names an anchor.

## Commands

```text
python3 -m unittest discover -s tests
124 tests passed

python3 -m compileall -q scripts tests
passed

git diff --check
passed
```
