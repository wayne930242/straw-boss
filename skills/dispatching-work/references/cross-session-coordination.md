# Cross-session coordination (`herdr-pane` only)

Two capabilities, both live-tested against a real herdr-pane worker: a worker reaching the orchestrator, and the orchestrator interrupting a worker mid-task to inject an urgent correction. Neither applies to `claude-p` — a headless print-mode process exits after one turn, so there is never a live process on the other end to message or interrupt.

**A worker's own judgment rule and `SendMessage` mechanics for reaching the orchestrator live in `notifying-boss` — the worker-facing skill, not here.** This file covers only what the orchestrator itself must do: make itself addressable (below) and, separately, interrupt a worker mid-task. Confirmed live: a worker sent a genuine API-design trade-off (two viable directions, a real cost/benefit on each) via `SendMessage` instead of `awaiting-user-input` — the orchestrator could not have answered it either, so even a successful delivery wouldn't have resolved anything correctly. This is exactly the failure mode `notifying-boss`'s Task 1 exists to prevent — every dispatch instruction points the worker at that skill rather than restating its judgment rule inline.

## Making the orchestrator addressable

`SendMessage`/`ListAgents` address live sessions by an auto-derived peer name (`<cwd-basename>-<random-suffix>`, e.g. `web-04`) — confirmed live this is **not** the `session_id` UUID; a raw `--session-id` value is never a valid `SendMessage` `to` target. `ListAgents` also excludes the caller's own session (self-listing), so the orchestrator cannot look up its own peer name the way it can a worker's.

Confirmed live: the orchestrator can make its own name deterministic by running `/rename straw-boss-orchestrator` on itself once — this works even on an already-running session (not just at `claude` launch), takes effect immediately, and is idempotent (renaming to the same name again is harmless). Do this once per orchestrator session, before the first `herdr-pane` dispatch that might need it — not per-plan, not per-task. `/rename` does not persist across a session restart, so a freshly restarted orchestrator session needs to do this again before it's reachable.

`/rename` is a Claude Code CLI slash command, not a tool call — the orchestrator cannot trigger it by emitting the text as part of its own response (that only reaches a human-typed input box, not the model's own output). Confirmed live: submit it to your own pane via `herdr agent prompt`, using the pane id `$HERDR_PANE_ID` already exported into the orchestrator's own environment:
```bash
herdr agent prompt "$HERDR_PANE_ID" "/rename straw-boss-orchestrator"
```
This queues as input for after the current turn (submitting to a `working` pane doesn't interrupt it), so the rename takes effect once this turn ends — no `--wait` needed, and there is nothing further to check for confirmation until the *next* turn (`herdr agent get "$HERDR_PANE_ID"`'s `terminal_title` will read `straw-boss-orchestrator` once it has).

Every `herdr-pane` dispatch instruction that might need this channel states: *"Your boss's peer name is `straw-boss-orchestrator` — use the `notifying-boss` skill if you need to reach it."* That's the whole instruction; `notifying-boss` itself carries the judgment rule and the never-authorization safety boundary, so it doesn't need restating here.

## Making a worker addressable

Confirmed live: `herdr agent start`'s trailing `-- --name <name>` flag (passed through to the underlying `claude` process, distinct from herdr's own `<unique-name>` control handle that's the command's first argument) sets the exact name that shows up in `ListAgents`/is reachable via `SendMessage`, overriding the auto-derived `<cwd-basename>-<suffix>` default entirely. `dispatch-mechanics.md`'s `herdr agent start` command already passes the same `plan_id`/`task_id`-derived value for both — no separate naming decision needed here.

## Mid-task interrupt and correction

Confirmed live: `herdr agent send-keys "<name>" esc` interrupts a currently-`working` turn and drops the worker back to `idle`, ready for a new prompt — matches Claude Code's own interactive Escape-to-interrupt behavior. Use this when the orchestrator learns of an urgent requirement change mid-task (from the user, typically) and needs to redirect a worker before it finishes its current turn, rather than waiting for it to finish first:

```bash
herdr agent send-keys "<name>" esc
herdr agent prompt "<name>" "<corrected instruction, stating what changed and why>" --wait --timeout <ms>
```

Confirm the interrupt actually landed (`herdr agent get "<name>"` reports `idle`, not still `working`) before sending the correction — sending a new prompt while the prior turn is still finishing queues behind it rather than replacing it.

**`claude-p` cannot be interrupted mid-flight.** There is no live process to send a key to once it's running — the only options are to let it finish and redispatch with corrected instructions afterward, or `TaskStop` the background task outright (discarding whatever it was mid-way through) and redispatch fresh. If a task dispatched as `claude-p` seems likely to need a mid-task correction, that's itself a reason to have used `herdr-pane` instead — see `dispatching-work`'s Task 1 mode-selection criteria.
