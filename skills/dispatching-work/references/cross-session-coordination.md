# Cross-session coordination

All agent-to-agent communication is instruction-keyed.
The caller supplies an instruction path and semantic intent; repository scripts resolve the endpoint, validate its provider-specific live fingerprint, deliver the message, and record the submission.
The main agent owns the loop and the worker owns the work: these messages carry facts, questions, and answers, while work direction stays inside the worker's own conversation with the user.

Live bodies carry one delta in at most two sentences.
Put longer context, instructions, or evidence behind repeatable `--ref`; the transport supplies identity, intent, and correlation.

## Record the main agent before launch

For every `herdr-pane` dispatch, record:

- `--main-agent-kind <claude|codex>`;
- `--main-agent-pane-id "$HERDR_PANE_ID"`;
- for Claude, `--main-agent-session-id <agent_session.value from herdr agent get>`;
- for Codex, `--main-agent-terminal-id <terminal_id>` and, when available, `--main-agent-session-id <agent_session.value>` from the same live record.

The pane is an address; the provider session proves which conversation occupies it.
Codex instructions with a recorded session continue across terminal restarts only when that same session remains in the recorded pane.
Older instructions without a session retain exact terminal matching.
A different or missing recorded session is a mismatch even if the terminal still matches.

`dispatch-task.py write` generates the instruction path and mandatory contract.
The task author does not reproduce communication prose in `--task`.

## Worker to main agent

Use [notifying-main-agent](../../notifying-main-agent/SKILL.md) for questions, checkpoints, progress, and outcomes.

## Main agent to worker

Send only explicit user direction, a verified cross-task fact, or the result of a coordinator-owned action.
Surface conflicts to the user; do not originate a competing work-detail decision.

Inform without interrupting:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <worker instruction path> \
  --to worker --intent inform --message "<delta>" \
  --ref "<source or artifact when needed>"
```

Resolve an interactive `awaiting-main-agent` through `reply-to-worker.py --reply "<delta>" --ref "<instruction/context when needed>"`; it validates, sends, and records the resolution.

Redirect carries an explicit user change or repairs an objectively wrong dispatch/dependency instruction.
Interrupt the recorded worker pane, confirm it is idle, then send the correction with `send-dispatch-message.py --to worker --intent redirect`.
Keep the correction short and reference longer replacement instructions.
The script owns the prompt; the lifecycle controller owns interruption.

## Cancel

Cancel means the user requested it or the dispatch is objectively invalid, duplicate, or unreachable—not that the main agent dislikes the worker's choice.

- Interactive: interrupt and close the recorded pane, then call `report-task-status.py --instruction-path ... --status cancelled`.

Inspect dependent Plan tasks immediately; `cancelled` does not satisfy a dependency.

## Main-agent self-compact

Self-compact is not cross-session communication.
Once all next-turn state is durable, the main agent may submit `/compact <focus>` to its own pane.
This does not replace any worker/main transport rule.

## Resume an older Codex dispatch

When terminal-only routing fails after a Herdr restart, inspect the original provider rollout to identify the main and worker sessions.
From the recorded main pane, run the single-record repair command with those original ids:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/rebind-dispatch.py" \
  --instruction-path <instruction> \
  --main-session-id <original-main-session> \
  --worker-session-id <original-worker-session> \
  --ref <original-main-rollout.jsonl> \
  --ref <original-worker-rollout.jsonl>
```

It checks the supplied rollout logs against the launch receipt, verifies the caller process and both live sessions, and atomically records the updated routing with its evidence, and preserves the launch receipt, contract, and task status.
A session already stored on the instruction remains binding.
Use original-session evidence for legacy records; a pane name or cwd is only a location.
Then reply through the normal instruction-keyed channel and let the worker report its own status.
