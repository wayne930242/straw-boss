# Anchor authority boundary verification

## Finding disposition

Every finding from the independent adversarial review of `1da9e55`+`7c00f06`.

| # | Finding | Disposition |
|---|---|---|
| A | Main agent fixing the reality anchor conflicts with the mandatory contract's verification-method grant | Boundary cut at category-versus-method and stated in `docs/roles.md`; every surface that grants a verification method now carries the scope, including the contract `dispatch_state` generates. `dispatching-work` Task 3's "or the reality anchor" allowed-list exception is deleted, not rewritten. This spec directory is the process artifact the finding named as missing |
| B | The stated reason a worker skips the claim is wrong, and following it reassigns the port | Reason replaced with the real mechanism (the lock carries no holder identity); pinned by a test that executes `claim-resource.py` |
| C | `orchestrator-worker`'s adoption conditions miss `work-on`'s confirmed-plan path | Adoption re-keyed on how many app-rooted workers run under one loop; a confirmed dependency graph and a capped batch are both named as this shape |
| D | `single-loop`'s "nothing else is scheduled against it" contradicts the blanket adversarial-review rule | Clause removed; the anchor's own check is stated never to change the graph. The blanket rule itself keeps no floor — that is the user's decision, recorded in `requirements.md` |
| E | "the coordinator's shape alone" is contradicted by the same file telling workers to use `bringing-coworker` | Red line removed; a worker plus one coworker is named as `single-loop`. A worker cannot reach `orchestrator-worker` structurally, so no prohibition is needed |
| F | A dispatch-time port has no release point on the batch/`done` path | Release rule stated once in `shared-resource-coordination.md`, covering every terminal status; `dispatching-work`'s Wrap-up branch and `plan-mechanics.md`'s auto-detach both point at it. `--ttl-seconds` guidance added for the extended holding window |
| G | The human anchor's "a finished article" contradicts "a human reading a document is review" | "finished article" removed; the human anchor covers an artifact the user *operates*, and with nothing to operate it routes to adversarial review, which removes the clash with "review is never the anchor" |
| H | Audit/research dispatches were forced to add an independent agent, unknown to the skills that own them | Adversarial review moved from "becomes the anchor" to "can serve as" it, matching the user's own wording, and read-only work is named as the case where it serves. `inspecting-app` and `investigating-app` each say so in their deliverable paragraph, with their evidence references named as what the review attacks. The anchor set stays closed at four so a main agent can always name one |
| I | The unknown-scope branch lost its isolation default, and tests forbade the file from mentioning risk | The mode stays the user's reading of the work (user decision), so no size-based default returns; instead `shipping-task` Task 2 states solo-mode's consequence when it offers the option, so the user answers informed. The clean-tree check and the one-solo-task-at-a-time rule remain the actual guard. The three negative assertions are gone |
| m1 | `troubleshooting-app` still said "It owns the flow decision" | Now "the mode decision" |
| m2 | `CONTEXT.md`'s Language section registered none of the new terms | **Coordination graph**, **reality anchor**, and **team-mode / solo-mode** registered with the terms they retire |
| m3 | Single-source-of-truth guarded by one `assertNotIn` | Replaced by counting the real `claim-port` command block across every skill file; exactly one holder |
| m4 | The lifecycle-mode surface list omitted `CONTEXT.md` and `scripts/` | Both added; `_Avoid_:` lines excluded so the glossary can name what it retires |
| m5 | Two line-length outliers from hand-inserted sentences | Both paragraphs rewrapped |

## Acceptance evidence

| Requirement | Evidence |
|---|---|
| One boundary, carried by every surface that grants a verification method | `test_every_grant_of_the_verification_method_is_scoped_to_the_anchor` builds a real contract via `dispatch_state.render_dispatch_contract` and requires the anchor scope in every such sentence across the contract and all prose surfaces, with a floor on how many grants exist |
| Both halves stated where authority is defined | `test_the_anchor_is_the_coordinators_and_the_method_inside_it_is_not` checks `docs/roles.md` and `choosing-graph` for the coordinator's half, the worker's half, and the testing default's escalation owner |
| The brief boundary and the injected stance agree | `test_task_authoring_leaves_work_definition_to_worker_and_user`, `test_prompt_authority_keeps_herdr_worker_independent`, and `test_session_start_primes_a_main_agent_with_a_compact_stance` each require the scope alongside the grant |
| One graph vocabulary everywhere | `test_graph_names_are_the_same_three_on_every_surface_that_lists_them` (zh-TW localization of the middle name accepted); retired names rejected |
| Only `orchestrator-worker` writes a plan | `test_only_orchestrator_worker_is_described_as_writing_a_dispatch_plan` |
| The anchor set is closed at four and identical everywhere | `test_the_anchor_set_is_closed_and_identical_on_every_surface` parses `choosing-graph`'s bullets and matches them against `docs/roles.md`'s enumeration |
| The worker never takes the anchor category | `test_no_surface_gives_the_worker_the_anchor_category` — the mirror of the scoping check, since a sentence handing the worker the anchor would otherwise satisfy it; the test asserts against its own rejection case |
| Read-only skills name their anchor | `test_read_only_dispatch_skills_name_the_anchor_their_evidence_feeds` |
| Every terminal path releases a dispatch-time claim | `test_a_dispatch_time_claim_is_released_from_every_terminal_path` checks the rule text plus both paths pointing at it |
| The documented reason a worker never re-claims | `test_the_same_holder_reclaiming_its_own_key_lands_on_another_port` runs `claim-resource.py` against an isolated `HOME`: same holder, same key, nothing listening, second claim lands on `base + 1` |
| The port mechanism lives in one place | `test_the_claim_port_command_is_written_out_exactly_once` |
| Lifecycle mode is the user's reading, answerable before scope is known | `test_the_lifecycle_mode_question_is_the_users_reading_of_the_work` |
| No retired lifecycle vocabulary anywhere live | `test_lifecycle_mode_names_are_consistent_across_every_live_surface`, extended to `CONTEXT.md` and `scripts/` |

## Do the new tests actually fail on the defect?

The reworked suite was run unchanged against `7c00f06`, the tree the review
examined, in a detached worktree:

```text
python3 -m unittest discover -s tests   # at 7c00f06, with this change's tests
118 tests, 12 failures
```

The red set is the three authority tests, the scoping test, the anchor-boundary
test, the closed-set test, the graph-vocabulary test, the plan-graph test, the
read-only-anchor test, the release test, the lifecycle-mode test, and the stance
test — twelve in all.
`test_lifecycle_mode_names_are_consistent_across_every_live_surface` is not one
of them: its pattern matches `full flow`/`light flow` only, and the phrasing
this change replaced was a bare "flow decision".

Two more are deliberately not in that set.
`test_no_surface_gives_the_worker_the_anchor_category` guards the drift this
change's own boundary makes possible — a surface handing the worker the anchor
category — which the reviewed tree did not have, so it asserts against its own
rejection case instead.

`test_the_same_holder_reclaiming_its_own_key_lands_on_another_port` passes on
`7c00f06` because `claim-resource.py` was never wrong — the prose describing it
was. It exists to fail the day someone adds a holder short-circuit that would
make the documented reason false.

## Commands

```text
python3 -m unittest discover -s tests
118 tests passed

python3 -m compileall -q scripts tests
passed

git diff --check
passed
```

## Relationship to the earlier dispatch specs

Two earlier specs record the grant without the scope.
`docs/specs/2026-08-26-agent-communication-contract/verification.md` records
"the worker and user choose specification, design, implementation, and
verification method" as verified, and
`docs/specs/2026-08-25-clear-dispatch-instructions/spec.md` states the same
grant as observable behavior. Both stand, refined: the verification method is
the method inside the reality anchor the dispatch names. The anchor category and
its checkpoint were never part of that grant, and this spec is where that scope
is now recorded.
