# Design

Spec: [spec.md](spec.md).

## Chosen approach

One new module, `scripts/straw_boss/dispatch/transfer.py`, owns moving a dispatch's coordinator route.
Two callers use it: `accept-orchestrator-handoff.py` (push) and the new `take-over-dispatch.py` (pull).
`handoff-orchestrator.py` uses its offer-side helpers to validate and snapshot the listed dispatches.

### Interface

- `Route`: the four unprefixed fields `herdr_pane_id`, `session_id`, `herdr_terminal_id`, `kind`.
- `route_of(instruction, prefix)` reads a route; prefixes are `main_agent_` and `root_main_agent_`.
- `caller_route()` proves the caller process runs in `HERDR_PANE_ID` (`validate_current_process_in_pane`) and returns that pane's live identity through `orchestrator.live_agents`, `current_agent`, and `agent_identity`.
- `offer_dispatches(paths, *, source_pane_id, retains_scope)` validates each listed dispatch with `validate_current_sender` on its `main` route, refuses unlisted owned in-progress dispatches when nothing is retained, and returns `[{instruction_path, route}]` snapshots.
- `move_main_routes(moves, new_route, *, reason, evidence)` takes `(path, expected_route | None)` pairs.
  It validates every dispatch first (top-level, `herdr-pane`, `in-progress`; expected route matches, or the route already names `new_route` when an expected route is given; the route differs from `new_route` when none is given), proves the rewritten `main` endpoint with `validate_live_session`, then writes each instruction and cascades to coworker `root_main_agent_*` routes.
  It returns `{moved: [{instruction_path, before}], already: [paths]}`.

Callers know only paths, the new route, and the audit reason; the invariants (state gate, snapshot compare, prove-before-write, re-read before write, coworker cascade, audit shape) stay inside the module.

### Data flow

1. Source: `handoff-orchestrator.py --dispatch <path>` → `offer_dispatches` → the handoff record gains `dispatches`.
2. Receiver: `accept-orchestrator-handoff.py` → drops listed paths whose file is gone into `skipped` → `caller_route()` → `move_main_routes(..., reason="orchestrator-handoff", evidence={source_pane_id, scope})` → marks the offer accepted with `transferred` and `skipped`.
   With no listed dispatches it makes no identity call, so existing handoffs keep their Herdr traffic.
3. Source: the accepted result carries `transferred_dispatches` into its compact report.
4. Takeover: `take-over-dispatch.py --user-requested --instruction-path ...` → `caller_route()` → `move_main_routes(..., reason="user-requested-takeover", evidence={"user_requested": true})` → reports each previous route and whether a live agent still carries it.

### Context renewal

`renewal.adopt_renewed_session` walks a per-role list of `(prefix, log_field)` pairs instead of one:
main agent `("main_agent_", "main_agent_adoptions")`, `("root_main_agent_", "root_main_agent_adoptions")`;
dispatched worker `("", "worker_adoptions")`, `("main_agent_", "main_agent_adoptions")`.
A route moves only where its pane and old session both match, the rule it already applies.

### Roll-call

The note for an uncorroborated coordinator names `adopt-dispatch.py` for the same conversation or pane and `take-over-dispatch.py` for another main agent at the user's request.

### Skills

- `handoff-orchestrator`: pass `--dispatch` for each in-progress dispatch in the moving scope.
- `boss-say` receive section: acceptance moves the listed dispatches to this pane.
- `dispatching-work/references/cross-session-coordination.md`: a takeover section, run only on the user's request, with the previous-coordinator notice through `contacting-orchestrators`.
- `dispatching-work/SKILL.md` and `CONTEXT.md` name the takeover.

## Precedent

- `adopt-dispatch.py`: prove-before-write, re-read before write, audit entry with before and after.
- `renewal.adopt_renewed_session`: pane-and-session match rule and per-role audit fields.
- `handoff-orchestrator.py --user-approved`: explicit user authority as a required flag.

## Alternatives considered

- A third mode inside `adopt-dispatch.py`.
  Rejected: adoption proves the same conversation or the same pane; a takeover rests on the user's request, and mixing the two proof models in one command blurs what each refusal means.
- Rewriting routes on the source side at offer time.
  Rejected: the receiver's identity only exists in its own pane, and a failed acceptance would leave dispatches pointing at a closed tab.

## Risks

- A crash between dispatch writes and marking the offer accepted leaves dispatches on the receiver while the source times out and closes the new tab.
  Acceptance is idempotent for routes that already name the receiver, so the receiver's retry completes it within the handoff window; outside it the takeover command recovers.
- `caller_route()` needs a readable identity; a Claude pane without a registry entry refuses rather than recording an unverifiable route.

## Method inside the reality anchor

Unittest-style tests under pytest against the fake Herdr: extend `tests/test_orchestrator_handoff.py`, `tests/test_context_renewal.py`, `tests/test_roll_call.py`, and add `tests/test_dispatch_takeover.py`; then run the full suite.

## Friction Notes

- Tried: quoting the user's Traditional Chinese replies verbatim in `decision.md` and `spec.md`.
  Found: `tests/test_skill_instruction_quality.py` requires the English surface, including `docs/specs/`, to be written in English.
  Led by: `aaaav-do` MINI-SDD `Approved from: <the user reply that approved it>`.
- Tried: `python3 -m unittest discover -s tests`.
  Found: `tests/` is not an importable package; the suite runs under pytest (`uv run --with pytest pytest tests`).
  Led by: none.
- Tried: restoring the original `renewal.py` with `git show HEAD:<path> > <path>` to prove the new tests fail on the old code.
  Found: zsh `noclobber` refuses `>` onto an existing file, so the first red run silently tested the new code; `>|` into the scratchpad and `cp` works.
  Led by: none.
