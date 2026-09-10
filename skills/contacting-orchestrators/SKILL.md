---
name: contacting-orchestrators
description: Use before this session's first dispatch, and whenever another main agent's work meets this one's.
---

## Register and find peers

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/register-orchestrator.py" \
  --scope '<one line describing this main agent’s work>'
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/register-orchestrator.py" --list
```

Register before the first dispatch and update the record when scope changes. Use live directory rows to resolve names or panes. A `live: false` row carries an `unavailable_reason`; a discovered row can receive messages before declaring its own scope. A pane with no verified identity remains unattributed.

## Exchange a delta

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-orchestrator-message.py" \
  --to <name-or-pane> --intent inform|question|answer \
  --message '<delta>' [--ref '<source>'] [--in-reply-to <id>]
```

Send one fact, question, or answer in at most two sentences; repeat `--ref` for supporting material. Reply to the incoming sender using its question id. Transport validates recipient identity and records delivery failures.

Accept a peer's conclusions within its owned scope. Verify the premises of your own actions, such as whether the required commit has landed on the integration branch. Conflicting facts go to the user; each task retains its current direction.

Route Straw Boss friction through [boss-assistant](../boss-assistant/SKILL.md#resolve-the-recipient).

**Complete when:** this session's scope is current and each owed delta is delivered or recorded undelivered.
