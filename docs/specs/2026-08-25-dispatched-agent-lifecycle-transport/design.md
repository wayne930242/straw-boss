# Dispatched-agent lifecycle and transport design

## Chosen seam

Use one generated dispatch contract, one launch adapter, and one internal
transport module. Keep existing status and checkpoint commands as semantic
wrappers so callers express intent without learning addressing details.

```text
dispatch-task.py write
  -> instruction.json + instruction.contract.md
  -> launch-dispatched-agent.py
     -> provider injection through herdr
     -> instruction.launch.json
  -> dispatch-task.py confirm

worker/main semantic command
  -> dispatch_transport.py
     -> resolve endpoint from instruction
     -> herdr agent get <recorded pane>
     -> require recorded session == live session
     -> herdr agent prompt <recorded pane> <message>
```

## Interfaces and adapters

### Dispatch contract

`dispatch-task.py write` owns contract rendering and hashing because it is the
last authoritative step before launch. The contract is stored beside the
instruction so it can be injected without changing the target repository.

Caller burden: supply task semantics plus the main agent's pane and session
identity. The caller does not construct lifecycle prose.

Verification surface: instruction/contract files and deterministic digest.

### Launch adapter

`launch-dispatched-agent.py` owns provider-specific startup arguments:

- Claude: `--append-system-prompt-file` points to the generated contract.
- Codex: `developer_instructions` receives the same contract content.

The adapter records the session returned by herdr. Confirmation binds this
receipt to the instruction, so starting an agent through another path is visible
as an incomplete dispatch rather than silently accepted.

Caller burden: instruction path, pane, agent name, and ordinary provider args.
No caller can omit or weaken injection.

Verification surface: fake-herdr argv capture and receipt matching.

### Shared transport

`dispatch_transport.py` owns instruction loading, target endpoint resolution,
live-session lookup, exact fingerprint validation, and herdr prompt execution.
Its target is `main` or `worker`; its address always comes from the instruction.

`send-dispatch-message.py` is the generic CLI. `report-task-status.py` and
`reply-to-worker.py` remain thin adapters because their state transitions and
delivery semantics are materially different from generic messaging.

Caller burden: instruction path, intent, and message only.

Verification surface: fake-herdr session lookup and prompt calls, including the
negative mismatch path.

### Stop guard

`dispatched-agent-stop-guard.py` is a Claude Stop hook. It resolves a dispatch
by the stopping session id and checks for a valid status artifact. A missing
report blocks Stop with the instruction-specific script command. Non-dispatched sessions are
unchanged.

Verification surface: hook JSON input/output for matched, unmatched, reported,
and unreported sessions.

## Alternatives considered

### Dynamically edit `CLAUDE.md` or `AGENTS.md`

Rejected. Those files belong to the target project, are loaded at session
startup with provider-specific precedence, and would create dirty-tree and
concurrency hazards. They also cannot prove which text a particular session
received.

### Let every dispatch prompt include workflow prose

Rejected. This is the current omission-prone shape: task authors can forget or
weaken the contract, and resume paths can diverge from initial launches.

### Keep separate routing implementations per command

Rejected. `report-task-status.py`, `reply-to-worker.py`, and
`get-main-agent.py` currently repeat JSON, herdr, and endpoint logic while
validating different identity subsets. The inconsistency is exactly what lets a
message reach a stale or wrong coordinator.

## Redundancy removal

- Replace repeated JSON/path/status helpers with a small shared state module.
- Replace all cross-session herdr subprocess construction with the transport
  module.
- Remove `get-main-agent.py`: exposing a raw endpoint is contrary to script-only
  transport.
- Remove `main_agent_send_message_peer` and all `SendMessage` fallback prose.
- Keep `report-task-status.py` and `reply-to-worker.py`; they are not redundant
  because they enforce distinct durable-state transitions around the common
  transport.
- Keep the plan watcher: it is durable recovery, not a duplicate live channel.

## Risks and controls

- A receipt could become stale if a pane is reused. Confirmation and every send
  independently compare the live session fingerprint.
- Herdr may succeed without proving the receiver processed a message. Existing
  reply transcript confirmation remains for checkpoints; durable status remains
  authoritative for task completion.
- A Stop hook can loop if its recovery instruction is unusable. It applies only
  to a resolved dispatched session and emits an exact repository command; hook
  implementation failures fail open for unrelated sessions.
- Codex lacks the same Stop lifecycle seam. The developer-level contract is
  enforced at launch, while process/status monitoring remains the recovery path.

## Applied precedent

- `CONTEXT.md`: main-agent dispatch authority and dispatched-agent outcome
  ownership.
- `docs/specs/2026-08-24-codex-plan-orchestration/`: persisted status plus
  watcher as provider-neutral recovery.
- Existing `report-task-status.py`: durable write before best-effort live
  notification.
