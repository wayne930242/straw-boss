# Cross-session coordination

All agent-to-agent communication is instruction-keyed. The caller supplies an
instruction path and semantic intent; repository scripts resolve the endpoint,
validate its live session fingerprint, deliver the message, and record the
submission. See `docs/roles.md` for inform/redirect/cancel authority.

## Record the main agent before launch

For every `herdr-pane` dispatch, record:

- `--main-agent-kind <claude|codex>`;
- `--main-agent-pane-id "$HERDR_PANE_ID"`;
- `--main-agent-session-id <agent_session.value from herdr agent get>`.

The pane is an address; the session id proves who currently occupies it. Both
are required so a reused pane cannot receive a stale task's message. Headless
dispatches have no live endpoint and rely on durable status plus process/watcher
observation.

`dispatch-task.py write` generates the instruction path and mandatory contract.
The task author does not reproduce communication prose in `--task`.

## Worker to main agent

Integrated/context questions and FYIs use:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <worker instruction path> \
  --to main --intent question|inform --message "<self-contained message>"
```

Checkpoints and outcomes use `report-task-status.py --instruction-path`; it
writes durable state before calling the same transport. If live delivery fails,
the written state remains authoritative.

Work-detail discussion and authorization go directly to the user in an
interactive task. The main agent relays only for a headless task.

## Main agent to worker

Inform without interrupting:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <worker instruction path> \
  --to worker --intent inform --message "<self-contained message>"
```

Resolve `awaiting-main-agent` through `reply-to-worker.py`; it validates the
checkpoint, sends through shared transport, confirms transcript delivery, and
records the resolution as one operation.

Redirect remains a two-part lifecycle operation: interrupt the recorded worker
pane, confirm it is idle, then send the correction with
`send-dispatch-message.py --to worker --intent redirect`. The script owns the
prompt; the lifecycle controller owns interruption.

## Cancel

Cancel means the dispatch itself was wrong, not that the worker failed.

- Interactive: interrupt and close the recorded pane, then call
  `report-task-status.py --instruction-path ... --status cancelled`.
- Headless: stop the tracked process, then write the same cancelled status.

Inspect dependent Plan tasks immediately; `cancelled` does not satisfy a
dependency.

## Main-agent self-compact

Self-compact is not cross-session communication. Once all next-turn state is
durable, the main agent may submit `/compact <focus>` to its own pane. This does
not replace any worker/main transport rule.

## Verification

- Every cross-session send names an instruction path, direction, intent, and
  message, but no pane id, agent name, or session id.
- A session mismatch is a hard failure before delivery.
- Every checkpoint and terminal outcome has durable status independent of live
  notification.
