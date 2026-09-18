Status: approved
Approved at: 2026-09-18
Approved from: the user's reply on 2026-09-18 asking to fix the renewal coworker-route problem as well, which approves this spec with that addition

# Cross-orchestrator dispatch transfer

Decisions: [decision.md](decision.md).

## Observable behavior

### Handoff carries the listed dispatches

1. `handoff-orchestrator.py` takes a repeated `--dispatch <instruction-path>`.
2. Before creating any tab, the source validates each listed dispatch: a top-level `herdr-pane` instruction with status `in-progress` whose `main` route the caller satisfies through `validate_current_sender`.
   A listed dispatch that fails is refused by path and reason.
3. When nothing is retained, the source also refuses while it owns an in-progress top-level dispatch that is not listed, and names each such instruction path.
   With `--retains`, unlisted dispatches stay with the source.
4. The handoff record stores each listed dispatch's instruction path and its `main_agent_*` route at offer time.
5. `accept-orchestrator-handoff.py` resolves the receiver's own kind, session, and terminal in its pane, then for each listed dispatch:
   - a dispatch whose instruction file is gone (wrapped up) is skipped and reported;
   - a dispatch whose route still equals the offer snapshot moves to the receiver;
   - a dispatch whose route already names the receiver counts as moved, so a repeated acceptance is idempotent;
   - any other route, or a status other than `in-progress`, refuses the whole acceptance, writes nothing, and leaves the offer `offered`.
6. Every move is validated before any write: the rewritten `main` route must pass `validate_live_session` against the receiver.
   Dispatches are written first, then the offer is marked `accepted`.
7. Acceptance prints the transferred and skipped instruction paths beside the scope.
8. After acceptance, every main-side command for a moved dispatch succeeds from the receiver pane and refuses from the source pane, and the worker's status reports deliver to the receiver pane.

### A user-requested takeover moves dispatches to the caller

1. `take-over-dispatch.py --user-requested --instruction-path <path> [--instruction-path <path> ...]` moves each listed dispatch's `main` route to the calling main agent.
2. Without `--user-requested` it refuses before reading any instruction.
3. The caller's process must run inside `HERDR_PANE_ID`; its kind, session, and terminal come from the live agent in that pane.
4. Each listed instruction must be a top-level `herdr-pane` dispatch with status `in-progress` whose route does not already name the caller.
   One failing dispatch refuses the call and writes nothing.
5. No liveness check gates the takeover.
   The output reports, per dispatch, the previous route and whether a live agent still carries the previous coordinator identity.
6. The skill instruction runs this command only when the user asks for a takeover, and informs a still-live previous coordinator through `contacting-orchestrators` which dispatches moved.

### Shared rules for both paths

1. A move rewrites `main_agent_herdr_pane_id`, `main_agent_session_id`, `main_agent_herdr_terminal_id`, and `main_agent_kind`; worker fields, contract, task, and status stay.
2. Each move appends `{at, reason, before, after, evidence}` to `main_agent_transfers`; `reason` is `orchestrator-handoff` (evidence: source pane and scope) or `user-requested-takeover`.
3. Each live coworker instruction whose `parent_instruction_path` names a moved dispatch and whose `root_main_agent_*` route equals the old route gets the same rewrite on its root fields, audited in `root_main_agent_transfers`.
4. The receiver's agent kind may differ from the previous coordinator's.

### Context renewal moves coworker routes

1. A renewed main agent moves `root_main_agent_session_id` on every coworker instruction whose `root_main_agent_herdr_pane_id` is its pane and whose root session is the old session, audited in `root_main_agent_adoptions`.
2. A renewed dispatched worker moves `main_agent_session_id` on every coworker instruction whose `main_agent_herdr_pane_id` is its pane and whose main session is the old session, audited in `main_agent_adoptions`.
3. Routes in other panes or naming other sessions stay untouched, as today.

### Roll-call guidance

When no live agent corroborates a dispatch's coordinator, the roll-call note names `adopt-dispatch.py` for the same conversation or pane and `take-over-dispatch.py` for a different main agent when the user asks for it.

## Edge cases

- A listed dispatch that is a coworker instruction is refused; it moves with its parent.
- A pending dispatch is refused on both paths; its own coordinator launches or wraps it up first.
- A handoff with no `--dispatch` and no owned in-progress dispatch behaves as today.
- A receiver whose identity Herdr cannot resolve refuses acceptance; the handoff retries and then closes only the new tab.

## Compatibility

- Instructions without `main_agent_transfers` stay valid; the field is appended on first move.
- A handoff that retains nothing now refuses while the source owns unlisted in-progress dispatches; before, it closed the source pane and left them unroutable.
- `adopt-dispatch.py` and `rebind-dispatch.py` keep their behavior.

## Non-goals

- Moving pending dispatches.
- Redelivering status reports already recorded as undeliverable.
- Sending the previous-coordinator notice from inside the script.

## Applied standards

- Fail-fast validation before any write, and prove-before-write of the new route, following `adopt-dispatch.py`.
- Scripts follow the existing `uv run --script`, argparse, JSON-stdout, `error:`-stderr pattern.
- Skill prose edits follow `writing-great-skills` and `tests/test_skill_instruction_quality.py`.

## Reality anchor

The executable lifecycle boundary: unittest-style tests, run under pytest, execute the real scripts against the fake Herdr in `tests/dispatched_agent_lifecycle_support.py`.
Checkpoint: a handoff with a listed dispatch is accepted, then `recover-task-status.py` succeeds from the receiver pane and refuses from the source pane, and a worker status report delivers to the receiver; a takeover from a third pane does the same and moves the coworker root route; a renewed main agent and a renewed parent worker each move the matching coworker route; the full test suite passes.
A live Herdr run is outside this checkpoint and is reported as a separate claim.
