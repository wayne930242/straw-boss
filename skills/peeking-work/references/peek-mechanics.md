# Peek mechanics

## Resolve the target

Use the canonical `~/.straw-boss/dispatch/<app>--<slug>.json` instruction, correlated by `plan_id`/`task_id` for a plan task. The instruction records `mode`, `session_id`, and `repo_root`; its launch receipt records the agent name and pane. Status carries progress and checkpoint metadata.

## Read the pane

```bash
herdr agent read "<agent-name>" --source recent --lines 60
```

This read leaves the pane and its input untouched. `recent` includes scrollback since the last state change; raise `--lines` if needed to understand the latest activity. Return the evidence to [peeking-work](../SKILL.md).
