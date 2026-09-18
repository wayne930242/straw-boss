# Cross-orchestrator dispatch transfer

Outcome: live dispatches move with their coordination scope to another main agent, both when the current main agent hands the scope off and when the user asks another main agent to take the work over.
Actors: the user, the source main agent, the receiving or taking-over main agent, dispatched workers and coworkers whose routes name the coordinator.

## Existing mechanisms

- `scripts/handoff-orchestrator.py` offers a continuity payload (goal, scope, state, next, decisions, terms, evidence, exclusions) to a new tab; `scripts/accept-orchestrator-handoff.py`, run through `boss-say`, marks the offer accepted. Neither reads or writes a dispatch instruction, and the source pane closes when nothing is retained.
- Every main-side command (`reply-to-worker.py`, `send-dispatch-message.py`, `recover-task-status.py`, `close-worker-pane.py`, a `cancelled` status report) validates the caller against the instruction's `main_agent_*` route through `validate_current_sender`; worker status reports deliver to that route and land in the delivery ledger as undeliverable when it is gone.
- `scripts/adopt-dispatch.py` covers a new Claude session in the recorded main pane and the recorded Claude session in a new pane; it refuses a different conversation in a different pane.
- `scripts/rebind-dispatch.py` repairs legacy Codex identities from launch-era rollout logs.
- `straw_boss.renewal.adopt_renewed_session` rewrites `main_agent_session_id` for same-pane context renewal.
- A coworker instruction names its parent worker as `main_agent_*` and the top-level coordinator as `root_main_agent_*`; coworker `done`/`failed` reports also deliver to `root-main`.
- `straw_boss.orchestrator.live_agents`, `current_agent`, and `agent_identity` resolve the caller pane's own kind, session, and terminal, including the Claude session registry fallback.
- `scripts/roll-call.py` notes a dispatch whose coordinator is not live and points at `adopt-dispatch.py`, which refuses when a different conversation runs the command.

## Decisions

| Question | Answer | Basis | Status |
|---|---|---|---|
| Are both push transfer (through handoff) and pull takeover (user-requested) in scope? | Yes. | User reply on 2026-09-18 asking for both. | confirmed |
| Which dispatch states transfer? | Top-level `herdr-pane` dispatches with instruction status `in-progress`; a pending dispatch is launched or wrapped up by its own coordinator first. | `adopt-dispatch.py` covers the same state; a pending dispatch has no live route yet. | grounded |
| Which routing fields move? | `main_agent_herdr_pane_id`, `main_agent_session_id`, `main_agent_herdr_terminal_id`, and `main_agent_kind` take the new coordinator's live identity; worker fields, contract, task, and status stay. | `resolve_endpoint` reads exactly these fields for the `main` target. | grounded |
| Do coworker routes move with their parent dispatch? | Yes: each coworker instruction whose parent moves gets the same rewrite on its `root_main_agent_*` fields. | Coworker terminal reports deliver to `root-main`; leaving it on the old coordinator makes them undeliverable. | grounded |
| Can the new coordinator be a different agent kind from the source? | Yes; the rewrite records the receiver's own kind and fingerprint. | `handoff-orchestrator.py --agent-kind` launches any supported kind. | grounded |
| How is each move audited? | Append `{at, reason, before, after, evidence}` to `main_agent_transfers` (and `root_main_agent_transfers` on coworkers); the handoff path or the user approval is the evidence. | `main_agent_adoptions` precedent in `adopt-dispatch.py`. | grounded |
| Who writes the handoff rewrite, and when? | The receiver, inside `accept-orchestrator-handoff.py`, after proving its own pane and identity; the source proves ownership of every listed dispatch when it makes the offer. | The receiver identity exists only in the new pane; the source identity is provable only in the source pane. | grounded |
| What happens when a listed dispatch changed between offer and acceptance? | A dispatch wrapped up in between is skipped and reported; a dispatch whose main route no longer matches the offer snapshot refuses the whole acceptance, and ownership stays with the source. | Fail-fast; the handoff script already retries and then closes only the new tab. | grounded |
| Which dispatches does a handoff carry? | The ones the source lists with a repeated `--dispatch`. A handoff that retains nothing refuses while the source still owns an unlisted in-progress dispatch and names each one; with `--retains`, unlisted dispatches stay with the source. | User answer on 2026-09-18 choosing the explicit list. | confirmed |
| Who decides that a takeover happens? | The user, by explicitly asking for it; the model never initiates or infers one. | User answer on 2026-09-18: the model does not judge a takeover; the user requests it. | confirmed |
| Does a takeover check whether the previous coordinator is gone? | No liveness gate. The command reports whether the previous coordinator identity is still carried by a live agent. | User answer on 2026-09-18: no confirmation needed. | confirmed |
| What happens when the previous coordinator is still live? | The takeover proceeds, and the new coordinator informs it through `contacting-orchestrators` which dispatches moved. | User answer on 2026-09-18: take over and notify. | confirmed |
| How is the user's request carried into a takeover? | A required `--user-requested` flag, recorded in the audit entry. | `handoff-orchestrator.py --user-approved` precedent. | grounded |
| Does one takeover call cover several dispatches? | Yes, a repeated `--instruction-path`; every listed dispatch is validated before any is written, and one refusal writes nothing. | Fail-fast; one gone coordinator usually leaves several dispatches. | grounded |
| Does roll-call point to the new command? | Yes: its note for a coordinator no live agent corroborates says a different coordinator takes the dispatch over only when the user asks, beside `adopt-dispatch.py` for the same conversation or pane. | The current note directs a different conversation to a command that refuses it. | grounded |
| Does same-pane context renewal also move coworker routes that name the renewing session? | Yes: a renewed main agent also moves coworker `root_main_agent_*` routes, and a renewed dispatched worker also moves its coworker's `main_agent_*` route, each only where pane and old session both match. | User reply on 2026-09-18 asking to fix this as well; `adopt_renewed_session` rewrites only the renewing role's own prefix. | confirmed |

Core rules readiness: Straw Boss authority lives in `skills/i-am-orchestrator/SKILL.md`, dispatch identity rules in `skills/dispatching-work/references/cross-session-coordination.md`, handoff flow in `skills/handoff-orchestrator/SKILL.md` and `skills/boss-say/SKILL.md`; no open decision remains.
