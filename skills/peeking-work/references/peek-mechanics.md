# Peek Mechanics

## Resolving the target

The canonical instruction is
`~/.straw-boss/dispatch/<app>--<slug>.json`. The instruction records mode,
session_id, and repo_root. For a plan task, correlate it by `plan_id` and
`task_id`. Its status record supplies progress state, note, optional evidence
references, timestamps, and checkpoint-resolution metadata rather than routing
data. The launch receipt records the agent name and pane for `herdr-pane`
dispatches. Read these artifacts before choosing the live-read mechanism.

## `herdr-pane`: `herdr agent read`

```
herdr agent read "<agent-name>" --source recent --lines 60
```

Read-only — does not interrupt a `working` pane, does not join it, does not consume input. `--source recent` is the default and is what you want for a peek (scrollback since the agent's last state change); `visible` only returns what's currently on-screen, which can be mid-scroll and miss the actual latest turn. Raise `--lines` for a task with a lot of recent tool output — 60 is enough to judge current activity for most tasks.

## Reporting back

State what the agent is currently doing in plain language, not a raw dump of the read/tail output. If the peek reveals the agent is visibly stuck on something its status file hasn't caught up to yet (e.g. a question sitting in the pane before `awaiting-user-input` synced), say so — but don't act on it from here; resolving it goes through the agent's own pane, or `dispatching-work`'s checkpoint handling, never this skill.
