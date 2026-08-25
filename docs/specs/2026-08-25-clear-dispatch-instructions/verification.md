# Clear dispatch instruction verification

## Requirement-to-evidence mapping

| Requirement | Evidence |
|---|---|
| Task briefs lead with a clear outcome and sufficient verified context | `test_task_authoring_guidance_prioritizes_outcome_and_context` passes against `shipping-task` and Plan mechanics |
| Possible implementations remain leads rather than boundaries | The same source-contract test requires the authoring rule in both standalone and Plan guidance |
| Generic lifecycle prose is not repeated in task briefs | The source-contract test rejects the former exhaustive checklist; contradiction scan finds the rule only in generated-contract specifications |
| Universal checkpoints come from the generated contract | `test_write_generates_a_hashed_system_contract_before_launch` verifies `awaiting-user-input`, `awaiting-main-agent`, and `awaiting-authorization` in a contract created by the public CLI |
| Existing lifecycle transport remains compatible | Full standard-library test suite passes |

## Automated evidence

- Red: the two focused tests initially failed because the generated contract
  lacked `awaiting-user-input`/`awaiting-authorization` and the skills still
  carried the exhaustive boilerplate checklist.
- Green: the same two focused tests passed after implementation.
- `python3 -m unittest discover -s tests`: 33 tests passed.
- `python3 -m compileall -q scripts tests`: passed.
- `openspec validate --specs --strict`: 6 specs passed, 0 failed.
- `git diff --check`: passed.

## Agent-operated interface observation

`dispatch-task.py write`, exercised by the integration test with an isolated
dispatch root, still creates the instruction plus hashed contract. The rendered
contract now selects checkpoints by the actor who can unblock the worker, while
the task value remains an outcome-oriented brief supplied by the caller.

## Human appropriateness verdict

Confirmed before implementation: the user defined good dispatching as clear
instructions plus sufficient context, without miscellaneous interference.

## Deviations and gaps

- No in-flight dispatch was redirected or rewritten, per explicit scope.
- No automatic prompt length or keyword gate was added; this is intentional to
  avoid replacing prose over-constraint with mechanical over-constraint.
- The user subsequently authorized a patch-version bump, commit, and push on
  2026-08-25. Tagging, a hosted release, deployment, and local plugin
  installation remain outside the requested scope.
