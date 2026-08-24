## Why

A dispatched agent that is blocked on something only its main agent's own judgment or dispatch authority can resolve (redispatching a failed dependency, arbitrating a peer/worktree conflict, deciding whether to redirect or cancel a related task) currently has no dedicated checkpoint for it.
Before this change, the only live channel for reaching the main agent was an informational, provider-specific message without durable checkpoint coverage. The current reporting contract now prefers the recorded herdr pane and permits `SendMessage` only for Claude-to-Claude fallback.
The result is that the one situation most needing the main agent's active attention is currently the least reliably surfaced, and there have been real cases of a dispatched agent's question being resolved only in the main agent's own reasoning, with the reply never actually sent back to the dispatched agent's pane or session.

## What Changes

- Add a third non-terminal checkpoint status, `awaiting-main-agent`, alongside the existing `awaiting-authorization` and `awaiting-user-input` — used when a dispatched agent is blocked pending an action only the main agent's own judgment or dispatch authority can take, as distinct from a fact-lookup question or a judgment call reserved for the user.
- `report-task-status.py`'s `VALID_STATUSES` gains `awaiting-main-agent`; the existing plan-task and standalone status-file mechanisms are reused unchanged.
- The provider-neutral Plan status stream gains `awaiting-main-agent`; on it, the main agent itself resolves the checkpoint (not "tell the user which pane to answer in").
- `wrap-up-task.py` refuses to archive a task while its status is `awaiting-main-agent`, matching the existing refusal for `awaiting-authorization`/`awaiting-user-input`.
- Add `scripts/reply-to-worker.py`, the main agent's required path for resolving an `awaiting-main-agent` checkpoint: one call resolves the worker's live pane, delivers the reply, confirms it landed, and records the resolution — so the main agent cannot "resolve" the checkpoint only in its own reasoning without the worker actually receiving anything.
- `dispatching-work`'s "Four checkpoint/report types" table gains this new row, with its own Red Flag entries.
- `notifying-main-agent` gains guidance on when a dispatched agent should escalate to this new checkpoint instead of the existing fire-and-forget informational-question channel.
- `dispatched-agent-escalation`'s escalation order gains a branch for "blocked pending the main agent's own action or authority," distinct from the existing "fact the main agent already has" and "judgment call reserved for the user" branches.

## Capabilities

### New Capabilities

(none — this change extends existing checkpoint/escalation/authority contracts rather than introducing a new one)

### Modified Capabilities

- `dispatch-completion-reporting`: the durable status stream and provider-specific fast reporting gain the new `awaiting-main-agent` checkpoint alongside the existing `done`/`failed`/`awaiting-authorization`/`awaiting-user-input`/`cancelled` set.
- `dispatch-authority`: the main agent gains a fourth authority action, `Resolve`, and a requirement to resolve a pending `awaiting-main-agent` checkpoint only through `reply-to-worker.py`, never an unstructured reply the worker might never actually receive.
- `dispatched-agent-escalation`: the escalation order gains a new branch — a dispatched agent blocked on something only the main agent's own judgment or dispatch authority can resolve uses the new `awaiting-main-agent` checkpoint instead of the fire-and-forget informational-question channel.

## Impact

- `scripts/report-task-status.py` — `VALID_STATUSES` addition.
- A new script, `scripts/reply-to-worker.py` — reachability lookup, reply delivery (`herdr agent prompt`), delivery confirmation, and resolution-record write, as one call.
- `scripts/wrap-up-task.py` — refusal-message text only (its terminal-status check already generalizes with no code change).
- `skills/dispatching-work/SKILL.md` — checkpoint table and Red Flags.
- `skills/dispatching-work/references/plan-mechanics.md` — new "Main-agent-action checkpoints" section, escalation order, instruction-assembly requirement, and watcher status list.
- `skills/notifying-main-agent/SKILL.md` — guidance distinguishing this checkpoint from the informational-question branch.
- `skills/shipping-task/SKILL.md` — instruction-assembly requirement and checkpoint-response handling (this skill assembles standalone dispatch instructions; without this, a standalone-flow worker has no way to learn the checkpoint exists).
- `skills/boss-say/SKILL.md` — batch-loop handling: resolves the checkpoint inline rather than treating it like `awaiting-authorization`/`awaiting-user-input`'s idle-and-report pattern.
- `docs/roles.md` — a fourth main-agent authority action, `Resolve`, alongside inform/redirect/cancel.
- `openspec/specs/dispatch-completion-reporting/spec.md`, `openspec/specs/dispatch-authority/spec.md`, `openspec/specs/dispatched-agent-escalation/spec.md` — requirement deltas.

The instruction-assembly requirement above is load-bearing, not optional documentation: a dispatched worker only learns this checkpoint exists from its own dispatch instruction text, not from the plugin's skill docs in the abstract — every skill that assembles a dispatch instruction (`plan-mechanics.md`'s plan-task assembly, `shipping-task`'s standalone assembly) has to state it explicitly, the same way each already does for `awaiting-user-input`.

The original change deferred worker-side bounded reminders and the polling loop's per-filename dedup bug. The 2026-08-24 provider-neutral Plan follow-up replaced that loop with a content-revision watcher, so checkpoint-to-terminal rewrites are now emitted; bounded worker reminders remain out of scope.
