# Dispatched-agent lifecycle and transport design

## Chosen seam

Use one generated dispatch contract, one launch adapter, and one internal
transport module. Keep existing status and checkpoint commands as semantic
wrappers so callers express intent without learning addressing details.

```text
dispatch-task.py write
  -> install/update ~/.straw-boss/bin/run-straw-boss-script.py
  -> instruction.json + instruction.contract.md
  -> launch-dispatched-agent.py
     -> provider injection through herdr
     -> instruction.launch.json
  -> dispatch-task.py confirm

worker/main semantic command
  -> version-neutral runtime launcher
     -> managed plugin: resolve currently enabled Straw Boss install
     -> source checkout: retain originating checkout
     -> resolution unavailable: fall back to originating root
  -> dispatch_transport.py
     -> resolve endpoint from instruction
     -> herdr agent get <recorded pane>
     -> accept recorded session == live Herdr session
     -> otherwise, for Claude only:
        -> herdr pane process-info --pane <recorded pane>
        -> require unique foreground Claude PID
        -> require Claude interactive registry PID/session match
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

The generated command targets a version-neutral launcher in
`~/.straw-boss/bin`, not a script beneath a versioned plugin cache. The contract
records the originating plugin or checkout root only as a compatibility
fallback. For a managed Claude or Codex plugin origin, the launcher asks the
plugin manager for the currently enabled `straw-boss@straw-boss` root on every
invocation, then executes the requested script from that root. Source-checkout
dispatches deliberately stay on their checkout so local development remains
deterministic.

The launcher is a shallow adapter: its public interface is `--origin-root`, an
optional `--prefer-installed`, one allowlisted `--script`, and the script's
remaining arguments. Session identity, routing, state transitions, and message
content remain behind the selected script. `dispatch-task.py write` installs it
atomically before writing any contract. A monotonic launcher-protocol marker
prevents an older still-running coordinator from downgrading a newer compatible
launcher.

Verification surface: a generated contract plus a fake plugin-manager listing
that points from an old cache root to a new one, with origin fallback when live
resolution is unavailable.

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
live-session lookup, exact fingerprint validation, narrowly scoped Claude
foreground-process corroboration, and herdr prompt execution. Its target is
`main` or `worker`; its address always comes from the instruction.

`send-dispatch-message.py` is the generic CLI. `report-task-status.py` and
`reply-to-worker.py` remain thin adapters because their state transitions and
delivery semantics are materially different from generic messaging.

Caller burden: instruction path, intent, and message only.

Verification surface: fake-herdr session/process lookup and prompt calls,
including polluted metadata recovery and genuine pane-reuse refusal.

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

### Trust Herdr's replacement session or rewrite the instruction

Rejected. In the observed failure Herdr's replacement value belongs to an SDK
worker, so rebinding would turn a false refusal into delivery to the wrong
session and weaken immutable dispatch identity.

### Patch the installed Herdr hook

Rejected as the product fix. The hook is managed by Herdr and overwritten on
integration reinstall or update. Straw Boss still needs a fail-closed transport
boundary while the upstream nested-session issue exists.

### Infer the receiver from pane name, cwd, or transcript recency

Rejected. These values can be shared across sessions and do not bind the live
foreground process to the dispatch's immutable session id.

### Keep absolute versioned script paths in the immutable contract

Rejected. The observed `calendar-event-model` completion report still invoked
the `0.18.0` cache after `0.18.2` was installed, so the fixed transport was never
entered. Contract immutability should preserve behavior and authority, not pin
implementation defects that a compatible patch update has corrected.

### Rewrite active contracts and launch receipts after an update

Rejected. Changing the contract digest and its historical receipt after launch
would falsely claim that the new contract was injected before the first model
turn. Dispatches created before the version-neutral launcher require a one-time
current-script command or a fresh dispatch; new contracts remain immutable and
gain update-safe execution through the launcher.

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
- Herdr's session fingerprint can be overwritten by a nested Claude SDK run.
  The fallback requires agreement among pane id, foreground process identity,
  Claude PID registry, interactive entrypoint, and expected session id. It does
  not use cwd, pane name, or the polluted Herdr value as replacement identity.
- A stale Claude registry file could survive after process exit. Corroboration
  considers only PIDs returned as live foreground processes by Herdr and requires
  the registry payload's PID to match its filename/process candidate. Missing or
  ambiguous evidence fails closed.
- Herdr may succeed without proving the receiver processed a message. Existing
  reply transcript confirmation remains for checkpoints; durable status remains
  authoritative for task completion.
- A Stop hook can loop if its recovery instruction is unusable. It applies only
  to a resolved dispatched session and emits an exact repository command; hook
  implementation failures fail open for unrelated sessions.
- Codex lacks the same Stop lifecycle seam. The developer-level contract is
  enforced at launch, while process/status monitoring remains the recovery path.
- A newer script could stop supporting an older instruction schema. Transport
  and status scripts therefore retain backward compatibility for active
  instruction files; if installed-root discovery fails or the requested script
  is absent, the launcher uses the recorded origin instead.
- The stable launcher is writable by the same local user who owns plugin and
  dispatch state. Its allowlist prevents contracts from turning it into an
  arbitrary script executor; filesystem compromise is outside this boundary.

## Applied precedent

- `CONTEXT.md`: main-agent dispatch authority and dispatched-agent outcome
  ownership.
- `docs/specs/2026-08-24-codex-plan-orchestration/`: persisted status plus
  watcher as provider-neutral recovery.
- Existing `report-task-status.py`: durable write before best-effort live
  notification.
- Herdr issue 672: upstream reproduction and security rationale for binding
  session reports to the pane's foreground process.
