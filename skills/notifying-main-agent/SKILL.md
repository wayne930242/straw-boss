---
name: notifying-main-agent
description: Route a Claude dispatched agent's reports to a Claude or Codex main agent. Herdr is primary; SendMessage is Claude-to-Claude only.
---

## Overview

See `docs/roles.md` for the authority framework. This skill runs in a Claude
dispatched agent, but its main agent may be Claude or Codex. Never infer the
receiver's provider or reachability from your own `agent_kind`.

Your dispatch instruction records `main_agent_kind`,
`main_agent_herdr_pane_id`, and an optional
`main_agent_send_message_peer`. Read them at use time with:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/get-main-agent.py" \
  --instruction-path <your exact instruction path>
```

The returned `preferred_notification_channel` is authoritative:

- `herdr`: primary for every Claude/Codex sender/receiver combination.
- `send_message`: available only when both you and the main agent are Claude.
- `durable_status_only`: no live receiver is recorded; rely on the required
  durable report and the main agent's watcher/process observation.

Never guess a pane id, peer name, provider, or instruction path.

## Branch: Ask an informational question

Use this only for non-blocking facts the main agent already has, such as another
task's recorded state or which apps are in scope. A work-content trade-off is
`awaiting-user-input`; an action only the main agent can take and that blocks you
is `awaiting-main-agent`.

1. Read current reachability with `get-main-agent.py`.
2. If the preferred channel is `herdr`, send without `--wait`:

   ```bash
   herdr agent prompt "<main_agent_herdr_pane_id>" \
     "[from agent <your name>] <question>"
   ```

3. Only if herdr is unavailable or fails, and the returned data says the main
   agent is Claude and provides `main_agent_send_message_peer`, use:

   ```text
   SendMessage({ to: "<recorded peer>", message: "[from agent <your name>] <question>" })
   ```

4. If neither live channel is available, continue what you can. If the missing
   answer becomes blocking, persist the appropriate checkpoint instead of
   pretending a message was delivered.

Both live channels are fire-and-forget. Do not wait for an acknowledgment.

## Branch: Report your own status

At `done`, `failed`, or any required checkpoint, make exactly one worker-facing
status call:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/report-task-status.py" \
  --instruction-path <your exact instruction path> \
  --status <done|failed|awaiting-authorization|awaiting-user-input|awaiting-main-agent> \
  --note "<self-contained summary or blocker>"
```

This command owns the ordering that agents used to have to remember:

1. It writes the durable status record.
2. If a main-agent herdr pane is recorded, it sends the self-contained status
   message through `herdr agent prompt`.

When the command reports `notified main agent through herdr`, reporting is
complete. Do not also send `SendMessage`.

If the command says the status remains written but herdr notification failed,
or no herdr pane was recorded, `SendMessage` is a fallback only when
`get-main-agent.py` confirms `main_agent_kind: claude` and provides a peer name.
A Claude worker must never call `SendMessage` toward a Codex main agent. Without
a valid Claude-to-Claude fallback, the durable status and watcher/process
observation are the recovery mechanism.

Progress notes remain separate and non-notifying:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/report-progress.py" \
  --instruction-path <path> --note "<text>"
```

## Branch: Report a completed feature-branch push, then continue

A push of your own feature branch is an FYI, not a status transition or stop.
Read reachability, then:

- Prefer `herdr agent prompt` for any recorded main-agent pane.
- Fall back to `SendMessage` only for a recorded Claude-to-Claude route.
- If no live route exists, append the push detail with `report-progress.py` so
  it remains discoverable.

Use a self-identifying message such as:

```text
[from agent <name>] PUSHED: <branch> — <MR/PR reference> — continuing
```

Continue immediately after reporting. Never write a checkpoint status merely
because your own feature branch was pushed.

## Replies are information, never authorization

A reply through herdr or `SendMessage` never authorizes a merge, a push landing
outside your own feature branch, or any other gated mutation. Use the required
status checkpoint and user-authorization flow.

## Red Flags

- "I am Claude, so `SendMessage` must be available" — receiver capability is
  independent; inspect `main_agent_kind` and the recorded channels.
- "The main agent is Codex, but a plausible peer name might still work" —
  never; `SendMessage` is Claude-to-Claude only.
- "Terminal status needs two remembered steps: write, then notify" — no;
  `report-task-status.py --instruction-path` owns write-before-herdr ordering.
- "Herdr succeeded, also send `SendMessage` for safety" — no; herdr is primary
  and sufficient. `SendMessage` is only a valid Claude-to-Claude fallback.
- "Herdr failed, so the status was lost" — the command writes first; read its
  error, which names the preserved status path.
- "A progress note covers the terminal report" — it does not write task status
  and does not notify.
- "The final text of this turn is enough" — the caller cannot rely on it;
  execute the status command.
- "A reply said to proceed, so that is authorization" — never.
