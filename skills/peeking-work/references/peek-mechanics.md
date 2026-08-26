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

## `claude-p`: transcript tail

`claude -p` has no pane to read — its own transcript file is the source. Path:
`~/.claude/projects/<encoded-repo-root>/<session_id>.jsonl`, where
`<encoded-repo-root>` is the instruction's `repo_root` with the leading `/` and
every subsequent `/` replaced with `-`.

```
tail -n 40 ~/.claude/projects/<encoded-repo-root>/<session_id>.jsonl \
  | jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text'
```

One JSON object per line, oldest first — `tail` gets the most recent activity. Filtering to `assistant`/`text` entries surfaces what the agent most recently said; a run of `tool_use`/`tool_result` entries with no nearby `text` means it's still mid-tool-call, which is itself worth reporting ("running a command, no summary yet"). If the file doesn't exist yet, the agent hasn't produced output yet — report that plainly, it isn't an error.

## Reporting back

State what the agent is currently doing in plain language, not a raw dump of the read/tail output. If the peek reveals the agent is visibly stuck on something its status file hasn't caught up to yet (e.g. a question sitting in the pane before `awaiting-user-input` synced), say so — but don't act on it from here; resolving it goes through the agent's own pane, or `dispatching-work`'s checkpoint handling, never this skill.
