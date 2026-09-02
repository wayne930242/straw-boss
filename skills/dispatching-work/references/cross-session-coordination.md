# Cross-session coordination

All agent-to-agent communication is instruction-keyed. The caller supplies an
instruction path and semantic intent; repository scripts resolve the endpoint,
validate its provider-specific live fingerprint, deliver the message, and
record the submission. See `docs/roles.md` for the **own the loop, not the
work** boundary.

Live bodies carry one delta in at most two sentences. Put longer context,
instructions, or evidence behind repeatable `--ref`; the transport supplies
identity, intent, and correlation.

## Record the main agent before launch

For every `herdr-pane` dispatch, record:

- `--main-agent-kind <claude|codex>`;
- `--main-agent-pane-id "$HERDR_PANE_ID"`;
- for Claude, `--main-agent-session-id <agent_session.value from herdr agent get>`;
- for Codex, `--main-agent-terminal-id <terminal_id from herdr agent get>`.

The pane is an address; the provider fingerprint proves which live agent occupies
it. Both are required so a reused pane cannot receive a stale task's message.
Claude's fingerprint is its session id. Herdr 0.8.0 does not expose a Codex
`agent_session`, so Codex uses Herdr's terminal id plus the reported agent kind;
that terminal id is not a Codex thread id. A headless dispatch has no live
endpoint; the status it persists before exiting carries the same events, and its
process exit marks completion.

`dispatch-task.py write` generates the instruction path and mandatory contract.
The task author does not reproduce communication prose in `--task`.

## Worker to main agent

Integrated/context questions and FYIs use:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <worker instruction path> \
  --to main --intent question|inform --message "<delta>" \
  --ref "<source or artifact when needed>"
```

Checkpoints and outcomes use `report-task-status.py --instruction-path`; it
writes durable state before calling the same transport. If live delivery fails,
the written state remains authoritative.

Work-detail discussion and authorization go directly to the user in an
interactive task. The Herdr worker is independent after launch, and the main
agent accepts user–worker decisions. Headless Codex relays through its recorded
thread; headless Claude reports terminal `failed` and starts a fresh attempt
after the user answers.

## Main agent to worker

Send only explicit user direction, a verified cross-task fact, or the result of
a coordinator-owned action. Surface conflicts to the user; do not originate a
competing work-detail decision.

Inform without interrupting:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <worker instruction path> \
  --to worker --intent inform --message "<delta>" \
  --ref "<source or artifact when needed>"
```

Resolve an interactive `awaiting-main-agent` through `reply-to-worker.py --reply
"<delta>" --ref "<instruction/context when needed>"`; it validates, sends, and
records the resolution. Headless Codex resumes its recorded thread with the
result. Headless Claude carries the result into a fresh attempt after terminal
`failed`.

Redirect carries an explicit user change or repairs an objectively wrong
dispatch/dependency instruction. Interrupt the recorded worker pane, confirm it
is idle, then send the correction with
`send-dispatch-message.py --to worker --intent redirect`. Keep the correction
short and reference longer replacement instructions. The script owns the prompt;
the lifecycle controller owns interruption.

## Cancel

Cancel means the user requested it or the dispatch is objectively invalid,
duplicate, or unreachable—not that the main agent dislikes the worker's choice.

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
  delta; longer material is a reference, never repeated prose.
- A provider fingerprint mismatch is a hard failure before delivery.
- Every checkpoint and terminal outcome has durable status independent of live
  notification.
