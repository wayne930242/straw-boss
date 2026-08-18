# Peek Mechanics

## Resolving the target

Every dispatch's instruction file (`~/.straw-boss/dispatch/<session_id>.json`, or the plan status file under `~/.straw-boss/plans/<slug>/status/<task_id>.json`) records: `mode` (`claude-p` / `herdr-pane`), `session_id`, `cwd` (the worktree or app directory dispatched into), and — for `herdr-pane` — the agent name used at dispatch (the same value as the trailing `claude --name` flag; see `dispatching-work`'s `dispatch-mechanics.md`). Read the instruction/status file first — never guess these values.

## `herdr-pane`: `herdr agent read`

```
herdr agent read "<agent-name>" --source recent --lines 60
```

Read-only — does not interrupt a `working` pane, does not join it, does not consume input. `--source recent` is the default and is what you want for a peek (scrollback since the agent's last state change); `visible` only returns what's currently on-screen, which can be mid-scroll and miss the actual latest turn. Raise `--lines` for a task with a lot of recent tool output — 60 is enough to judge current activity for most tasks.

## `claude-p`: transcript tail

`claude -p` has no pane to read — its own transcript file is the only source. Path: `~/.claude/projects/<encoded-cwd>/<session_id>.jsonl`, where `<encoded-cwd>` is the dispatch's `cwd` with the leading `/` and every subsequent `/` replaced with `-` (confirmed convention — this is the same scheme Claude Code uses for every session's own transcript path).

```
tail -n 40 ~/.claude/projects/<encoded-cwd>/<session_id>.jsonl \
  | jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text'
```

One JSON object per line, oldest first — `tail` gets the most recent activity. Filtering to `assistant`/`text` entries surfaces what the worker most recently said; a run of `tool_use`/`tool_result` entries with no nearby `text` means it's still mid-tool-call, which is itself worth reporting ("running a command, no summary yet"). If the file doesn't exist yet, the worker hasn't produced output yet — report that plainly, it isn't an error.

## Reporting back

State what the worker is currently doing in plain language, not a raw dump of the read/tail output. If the peek reveals the worker is visibly stuck on something its status file hasn't caught up to yet (e.g. a question sitting in the pane before `awaiting-user-input` synced), say so — but don't act on it from here; resolving it goes through the worker's own pane, or `dispatching-work`'s checkpoint handling, never this skill.
