# Verification

Spec: [spec.md](spec.md).
Evidence runs the real scripts against the fake Herdr in `tests/dispatched_agent_lifecycle_support.py`; its `HERDR_ACCEPT_HANDOFF_SCRIPT` branch runs the real `accept-orchestrator-handoff.py` in the receiver pane during a real `handoff-orchestrator.py` run.

## Requirements

| Requirement | Evidence | Result |
|---|---|---|
| Handoff 1: `--dispatch` is accepted and carried | `test_accepted_handoff_moves_listed_dispatches_to_the_receiver`: output `transferred_dispatches` names the listed instruction | pass |
| Handoff 2: a listed dispatch the caller does not coordinate is refused before any tab | `test_handoff_refuses_a_listed_dispatch_this_pane_does_not_coordinate`: `session mismatch`, no `tab create` call | pass |
| Handoff 3: nothing retained refuses over an unlisted owned dispatch; `--retains` leaves it with the source | `test_handoff_refuses_to_close_the_source_over_an_unlisted_dispatch` (path named, no `tab create`); `test_retained_handoff_leaves_unlisted_dispatches_with_the_source` (instruction byte-identical) | pass |
| Handoff 4: the offer snapshots each route | Snapshot compare drives `test_acceptance_refuses_a_dispatch_whose_route_changed_after_the_offer` and the end-to-end move | pass |
| Handoff 5: skip wrapped, move matching, idempotent already-moved, refuse changed route with nothing written | `test_acceptance_skips_a_wrapped_dispatch_and_completes_an_interrupted_move`; `test_acceptance_refuses_a_dispatch_whose_route_changed_after_the_offer` (offer stays `offered`, files unchanged) | pass |
| Handoff 5: a status other than `in-progress` refuses | Shared `load_movable`; exercised through `test_one_refused_dispatch_writes_nothing` on the takeover path, not on the acceptance path | pass |
| Handoff 6: the new route is proven before any write | `test_acceptance_refuses_a_receiver_herdr_cannot_identify`: no live agent in `new-pane`, offer stays `offered`, files unchanged | pass |
| Handoff 7: acceptance prints transferred and skipped paths | Both acceptance tests read `transferred_dispatches` and `skipped_dispatches` from stdout | pass |
| Handoff 8: receiver commands succeed, source refused, worker reports reach the receiver | End-to-end test: `report-task-status.py awaiting-main-agent` prompts only `new-pane`; `recover-task-status.py` refuses from `main-pane` with `sender pane mismatch` and succeeds from `new-pane`; source pane closed last | pass |
| Takeover 1–3: moves listed dispatches to the caller proven in its pane; refuses without `--user-requested` | `test_takeover_moves_the_dispatch_and_its_coworker_root_to_the_caller`; `test_takeover_refuses_without_the_users_request` (file unchanged) | pass |
| Takeover 4: one refused dispatch writes nothing; an already-routed dispatch is refused | `test_one_refused_dispatch_writes_nothing`; `test_takeover_refuses_a_dispatch_already_routed_to_the_caller` | pass |
| Takeover 5: no liveness gate; reports whether the previous coordinator is live | `test_takeover_proceeds_and_reports_a_previous_coordinator_that_is_still_live` (`true`, route moved); the move test reports `false` | pass |
| Takeover 6: the skill runs it only on the user's request and informs a live previous coordinator | Review of `skills/dispatching-work/references/cross-session-coordination.md` takeover section | pass (review) |
| Shared 1–2: four route fields move, worker fields stay, audit entry appended | Move tests assert route, `session_id` of the worker, and `main_agent_transfers` reason, before, and evidence | pass |
| Shared 3: coworker root route moves with its parent | Handoff end-to-end and takeover move tests assert `root_main_agent_*` and `root_main_agent_transfers`; coworker `main_agent_*` stays on the parent worker | pass |
| Shared 4: the new coordinator may be another agent kind | `test_a_codex_coordinator_takes_over_a_claude_coordinators_dispatch`: `main_agent_kind` becomes `codex`, then `recover-task-status.py` succeeds from the Codex pane | pass |
| Renewal 1: a renewed main agent moves coworker root routes | `test_renewed_main_agent_moves_its_coworkers_root_route`; fails on the original `renewal.py` (`'main-session' != 'renewed-main'`) | pass |
| Renewal 2: a renewed parent worker moves its coworker's main route | `test_renewed_parent_worker_moves_its_coworkers_main_route`; fails on the original `renewal.py` (`'worker-session' != 'renewed-worker'`) | pass |
| Renewal 3: other panes and sessions stay untouched | Existing `test_renewed_worker_adopts_only_its_own_route` still passes; the renewal tests assert unrelated route fields unchanged | pass |
| Roll-call names both commands | `test_a_coordinator_nothing_corroborates_names_adoption_and_user_requested_takeover` | pass |
| Full suite | `uv run --with pytest pytest -q tests`: 402 passed, 177 subtests passed | pass |

## Human appropriateness

No UI or human-use surface changed; skill prose changes were reviewed against `writing-great-skills` and pass `tests/test_skill_instruction_quality.py`.

## Deviations

- Duplicate `--dispatch` or `--instruction-path` entries are collapsed to one; the spec does not mention duplicates.

## Verification gaps

- A live Herdr run of a real handoff and a real takeover was not performed; all evidence uses the fake Herdr.
- Commit, push, and plugin install are separate claims reported with their own evidence.

## Reflexive

- Quoting the user's replies verbatim in `docs/specs/`: gap — no Straw Boss instruction states that `docs/specs/` is English-only; only `tests/test_skill_instruction_quality.py` enforces it.
  Placed in the new root `AGENTS.md`.
- Running the suite with `unittest discover`: gap — no Straw Boss instruction names the test command.
  Placed in the new root `AGENTS.md`.
- Restoring a file with `>` under zsh `noclobber`: gap — a general tool-use slip no project or skill owns; no placement.
