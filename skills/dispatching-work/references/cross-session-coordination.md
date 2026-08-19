# Cross-session coordination

Three capabilities, all live-tested: an agent reaching its main agent (`herdr-pane` primary channel, `SendMessage` fallback and the only channel `claude-p` has), and the main agent interrupting an agent mid-task to inject an urgent correction (`herdr-pane` only — see "Mid-task interrupt and correction" below for why `claude-p` can't do this one).

**An agent's own judgment rule and send mechanics for reaching its main agent live in `notifying-boss` — the agent-facing skill, not here.** This file covers only what the main agent itself must do: make itself addressable, two ways (below), and, separately, interrupt an agent mid-task. Confirmed live: an agent sent a genuine API-design trade-off (two viable directions, a real cost/benefit on each) via `SendMessage` instead of `awaiting-user-input` — the main agent could not have answered it either, so even a successful delivery wouldn't have resolved anything correctly. This is exactly the failure mode `notifying-boss`'s Task 1 exists to prevent — every dispatch instruction points the agent at that skill rather than restating its judgment rule inline.

## Making the main agent addressable

Two independent addressing schemes, not interchangeable — an agent uses whichever one its own dispatch mode actually has:

**herdr pane id (primary, `herdr-pane` agents only).** The main agent's own `$HERDR_PANE_ID` (e.g. `wF:p9`) is a valid `herdr agent get`/`herdr agent prompt` target regardless of whether that pane was ever named via `herdr agent start` — confirmed live: `herdr agent list`/`herdr agent get "$HERDR_PANE_ID"` return the main agent's own entry with no `name` field at all when it wasn't started that way, `pane_id` alone still resolves it. Nothing needs to be set up for this in advance; the main agent's dispatch instruction just states its own current `$HERDR_PANE_ID` value literally, resolved at instruction-assembly time (not the literal string `$HERDR_PANE_ID` — its actual value).

**`SendMessage` peer name (fallback for `herdr-pane`, the only option for `claude-p`).** `SendMessage`/`ListAgents` address live sessions by an auto-derived peer name (`<cwd-basename>-<random-suffix>`, e.g. `web-04`) — this is **not** the `session_id` UUID; a raw `--session-id` value is never a valid `SendMessage` `to` target. `ListAgents` also excludes the caller's own session (self-listing, unlike `herdr agent list`), so the main agent cannot look up its own peer name the way it can an agent's — it sets one instead.

Confirmed live: the main agent can make its own peer name deterministic by running `/rename straw-boss-orchestrator` on itself once — this works even on an already-running session (not just at `claude` launch), takes effect immediately, and is idempotent (renaming to the same name again is harmless). Do this once per main-agent session, before the first dispatch that might need this channel — not per-plan, not per-task. `/rename` does not persist across a session restart, so a freshly restarted main-agent session needs to do this again before it's reachable.

`/rename` is a Claude Code CLI slash command, not a tool call — the main agent cannot trigger it by emitting the text as part of its own response (that only reaches a human-typed input box, not the model's own output). Confirmed live: submit it to your own pane via `herdr agent prompt`, using the pane id `$HERDR_PANE_ID` already exported into the main agent's own environment:
```bash
herdr agent prompt "$HERDR_PANE_ID" "/rename straw-boss-orchestrator"
```
This queues as input for after the current turn (submitting to a `working` pane doesn't interrupt it), so the rename takes effect once this turn ends — no `--wait` needed, and there is nothing further to check for confirmation until the *next* turn (`herdr agent get "$HERDR_PANE_ID"`'s `terminal_title` will read `straw-boss-orchestrator` once it has).

**What the dispatch instruction states, per mode:**
- `herdr-pane`: *"Your main agent's herdr pane id is `<resolved $HERDR_PANE_ID value>` and its `SendMessage` peer name is `straw-boss-orchestrator` — use the `notifying-boss` skill if you need to reach it."*
- `claude-p`: *"Your main agent's `SendMessage` peer name is `straw-boss-orchestrator` — use the `notifying-boss` skill if you need to reach it, but you cannot wait for a reply before you exit."*

That's the whole instruction either way; `notifying-boss` itself carries the judgment rule, the channel-selection logic, and the never-authorization safety boundary, so none of it needs restating here.

## Making an agent addressable

`herdr agent start`'s trailing `-- --name <name>` flag (passed through to the underlying `claude` process, distinct from herdr's own `<unique-name>` control handle that's the command's first argument) sets the exact name that shows up in `ListAgents`/is reachable via `SendMessage`, overriding the auto-derived `<cwd-basename>-<suffix>` default entirely. `dispatch-mechanics.md`'s `herdr agent start` command already passes the same `plan_id`/`task_id`-derived value for both — no separate naming decision needed here.

## Mid-task interrupt and correction

Confirmed live: `herdr agent send-keys "<name>" esc` interrupts a currently-`working` turn and drops the agent back to `idle`, ready for a new prompt — matches Claude Code's own interactive Escape-to-interrupt behavior. Use this when the main agent learns of an urgent requirement change mid-task (from the user, typically) and needs to redirect an agent before it finishes its current turn, rather than waiting for it to finish first:

```bash
herdr agent send-keys "<name>" esc
herdr agent prompt "<name>" "<corrected instruction, stating what changed and why>" --wait --timeout <ms>
```

Confirm the interrupt actually landed (`herdr agent get "<name>"` reports `idle`, not still `working`) before sending the correction — sending a new prompt while the prior turn is still finishing queues behind it rather than replacing it.

**`claude-p` cannot be interrupted mid-flight.** There is no live process to send a key to once it's running — the only options are to let it finish and redispatch with corrected instructions afterward, or `TaskStop` the background task outright (discarding whatever it was mid-way through) and redispatch fresh. If a task dispatched as `claude-p` seems likely to need a mid-task correction, that's itself a reason to have used `herdr-pane` instead — see `dispatching-work`'s Task 1 mode-selection criteria.
