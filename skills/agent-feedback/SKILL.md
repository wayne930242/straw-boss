---
name: agent-feedback
description: Use when locating the boss-assistant, or when the directory has none live and one needs to be opened.
---

## Find it

List the directory through [contacting-orchestrators](../contacting-orchestrators/SKILL.md#register-and-find-peers).
The current assistant is the row with `role` set to `boss-assistant` and `live: true`.
A row that carries the role but is not live is a dead claim; treat the role as unclaimed, not as identifying that row.
More than one live row carrying the role is a registration race: ask the user which one to keep, and release the others with `--release-role` from their own sessions.

## Open one when none exists

Ask whether this session should take the role, unless the user already named a session for it.
This session claims it, alongside its own scope:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/register-orchestrator.py" \
  --scope '<one line describing this session's main work>' --role boss-assistant
```

For a separately approved window instead, use [handoff-orchestrator](../handoff-orchestrator/SKILL.md); the receiver claims the role with the same command once it accepts.

## Release it

A session that stops holding the role drops it without rewriting its scope:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/register-orchestrator.py" --release-role
```

**Complete when:** the assistant is identified live and reachable, or a fresh claim is registered and confirmed in the directory.
