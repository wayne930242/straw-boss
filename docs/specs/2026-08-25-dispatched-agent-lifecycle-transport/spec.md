# Dispatched-agent lifecycle and transport specification

## Observable contract

- `dispatch-task.py write` creates the instruction and a sibling immutable
  contract before any agent launch. The instruction records the contract path
  and SHA-256 digest.
- A herdr-addressable main agent must have both a pane id and a session id in a
  new instruction. Endpoint identity is incomplete without the session id.
- `launch-dispatched-agent.py` is the supported interactive launcher. It passes
  Claude `--append-system-prompt-file <contract>` or Codex
  `-c developer_instructions=<contract-content>` through herdr and writes a
  launch receipt only after herdr returns the launched session identity.
- `dispatch-task.py confirm` requires a launch receipt whose instruction path,
  contract digest, pane id, agent kind, and live session id match the proposed
  confirmation. A mismatch does not change instruction state.
- `send-dispatch-message.py --instruction-path ... --to main|worker` is the
  generic live-message interface. It accepts message intent and content, but no
  endpoint identifier.
- Before prompting, shared transport loads the target pane and expected session
  from the instruction, calls `herdr agent get`, and requires the live
  `agent_session.value` to match exactly. If it differs and the recorded agent
  kind is Claude, transport may instead corroborate the expected session by:
  calling `herdr pane process-info --pane <pane>`; selecting the pane's unique
  foreground `claude` process; and requiring
  `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/sessions/<pid>.json` to identify that
  same PID, the expected session id, `kind: interactive`, and `entrypoint: cli`.
  It prompts the recorded pane only when one of those validation paths passes.
- `report-task-status.py` writes durable state before using shared transport to
  notify the main agent. Delivery failure never rolls back that write.
- `reply-to-worker.py` retains checkpoint-state validation and delivery
  confirmation, while delegating endpoint resolution and initial send to shared
  transport.
- The Claude Stop hook blocks only sessions matching an in-progress dispatch
  that has no valid checkpoint or terminal status. Its reason includes the
  instruction-specific status command.
- Documentation and skills instruct agents to use repository scripts; direct
  `SendMessage` and direct cross-session `herdr agent prompt` are absent.

## Contract content

Each generated contract states:

- the canonical instruction path;
- that all reports, questions, replies, redirections, and cancellations use the
  supplied scripts rather than provider-native messaging;
- the exact progress and status commands;
- that `awaiting-main-agent` is required when the agent cannot safely continue;
- that a terminal `done` or `failed` report is required before stopping;
- that an agent must continue after a checkpoint reply or report a new blocking
  state rather than becoming silently idle.

## Compatibility and failure behavior

- Existing instruction files remain readable for inspection and cancellation,
  but cannot be newly confirmed without a matching launch receipt.
- Legacy plan/task-only status writes remain durable and omit live notification
  because they do not identify a dispatch.
- Missing herdr, malformed JSON, an absent receiver session, session mismatch,
  or prompt failure returns non-zero with an actionable error.
- A session mismatch with missing, ambiguous, malformed, SDK-only, or
  disagreeing foreground-process evidence remains a refusal. Codex and unknown
  agent kinds retain exact Herdr fingerprint validation only.
- A main-agent session mismatch is never downgraded to watcher-only success or
  accepted by rebinding the instruction to Herdr's reported session.
- Durable plan status and `watch-plan-status.py` remain the recovery and
  scheduling authority.

## Non-goals

- Live messages do not grant authorization or alter task ownership.
- Transport does not decide whether a question should go to the user, main
  agent, or a peer; semantic wrappers enforce those role rules.
- The contract does not modify target-project instruction files.

## Correctness strategy

Standard-library integration tests invoke public script CLIs with temporary
dispatch roots and a fake herdr executable. They verify contract generation,
provider-specific injection, receipt-gated confirmation, two-way session
validation, foreground Claude corroboration after SDK metadata pollution,
continued refusal after genuine pane reuse, write-before-notify ordering,
Stop-hook behavior, and the absence of public direct-routing instructions. The
full unit suite, Python compilation, OpenSpec validation, and repository
contradiction scans complete verification.

## Applied standards and evidence

- [Herdr issue 672](https://github.com/herdrdev/herdr/issues/672): documents
  nested/headless Claude inheriting `HERDR_PANE_ID` and overwriting a pane's
  stored session because the integration report lacks process identity. This
  change corroborates process identity at the transport boundary without
  weakening pane-reuse refusal.
- `AGENTS.md` working agreements supplied for this workspace: read before write,
  TDD for source changes, scoped edits, and relevant verification.

User confirmation of this amended specification: 2026-08-25.
