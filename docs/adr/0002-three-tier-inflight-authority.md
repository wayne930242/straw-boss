# Three-tier authority over in-flight dispatched work: inform, redirect, cancel

The main agent may act on discoveries it makes about a task it already dispatched, without asking the user first (as long as it doesn't diverge substantially from the user's stated direction), but the three ways it can act have different blast radii and needed distinct names and mechanics: **inform** (FYI, no interruption — `herdr agent prompt` without `esc`, queues behind the current turn), **redirect** (interrupt and correct the same task — the existing `esc` + reprompt mechanism, unchanged), and **cancel** (end the dispatch outright because the dispatch itself, not the worker's execution, was wrong). Cancel gets its own `cancelled` terminal status rather than reusing `failed`, because `failed` already carries specific meaning (the worker's own attempt went wrong) that `plan-mechanics.md`'s permission-denial check and `boss-say`'s failure reporting depend on — conflating a main-agent-initiated stop into it would corrupt both.

Cancel is supported for both dispatch modes. `herdr-pane`: interrupt (`send-keys esc`) then close pane/tab/worktree without expecting further output. `claude-p`: `TaskStop` on the backgrounded process — discovered during implementation that `cross-session-coordination.md` already documented exactly this mechanism (`TaskStop` a backgrounded `claude-p` task, discarding its mid-way progress) as one of the two options when a `claude-p` task needs a correction it can't receive live. Cancel reuses that same mechanism, just recording `cancelled` instead of redispatching fresh — no new capability had to be built, only a documented one repurposed and named.

## Status

Accepted

## Consequences

- `read-plan-status.py`, `wrap-up-task.py`, and the `Monitor` polling loop's status vocabulary all need to recognize `cancelled` alongside `done`/`failed` as terminal, for both dispatch modes.
- No asymmetry between dispatch modes to document or later revisit — both support cancel from day one.
