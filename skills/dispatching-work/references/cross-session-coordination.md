# Cross-session coordination

Several capabilities, all live-tested: an agent reaching its main agent (`herdr-pane` primary channel, `SendMessage` fallback and the only channel `claude-p` has), and the main agent's three-tier authority over a task it already dispatched — see `docs/roles.md` for the cast/naming/authority framework these implement, not redefined here — **inform** (below), **redirect** (below, `herdr-pane` only), and **cancel** (below, both modes).

**Claude's own judgment rule and `SendMessage` mechanics live in `notifying-main-agent`; Codex instructions inline the equivalent status/checkpoint contract because Codex does not load Claude skills.** This file covers what the main agent must do: make the applicable addressing surfaces available and act on in-flight sessions. Provider-neutral Plan outcomes always travel through `report-task-status.py` plus `watch-plan-status.py`; provider messaging is additive.

## Making the main agent addressable

Two independent addressing schemes, not interchangeable — an agent uses whichever one its own dispatch mode actually has:

**herdr pane id (primary, `herdr-pane` agents only).** The main agent's own `$HERDR_PANE_ID` (e.g. `wF:p9`) is a valid `herdr agent get`/`herdr agent prompt` target regardless of whether that pane was ever named via `herdr agent start` — confirmed live: `herdr agent list`/`herdr agent get "$HERDR_PANE_ID"` return the main agent's own entry with no `name` field at all when it wasn't started that way, `pane_id` alone still resolves it. Nothing needs to be set up for this in advance; the main agent's dispatch instruction just states its own current `$HERDR_PANE_ID` value literally, resolved at instruction-assembly time (not the literal string `$HERDR_PANE_ID` — its actual value).

**`SendMessage` peer name (fallback for `herdr-pane`, the only option for `claude-p`).** `SendMessage`/`ListAgents` address live sessions by an auto-derived peer name (`<cwd-basename>-<random-suffix>`, e.g. `web-04`) — this is **not** the `session_id` UUID; a raw `--session-id` value is never a valid `SendMessage` `to` target. `ListAgents` also excludes the caller's own session (self-listing, unlike `herdr agent list`), so the main agent cannot look up its own peer name the way it can an agent's — it sets one instead.

**Check whether this session already has one, before setting a new one.** If this main-agent session's own `claude` process was launched with a `--name <value>` flag (the same launch-args inspection `dispatch-mechanics.md`'s "Detecting the main agent's own permission mode" already does, and the same flag `"Making an agent addressable"` below documents as what makes a session `SendMessage`/`ListAgents`-addressable), that value already is this session's peer name — stable across a `/compact`, and across a process restart too as long as the relaunch reuses the same `--name`, unlike a `/rename`d value or a pane-id-derived suffix, both of which are lost the moment this session's own process restarts. Detect it the same way:
```bash
ORCH_ARGS=$(ps -p "$CLAUDE_PID" -ww -o args= 2>/dev/null)
MAIN_AGENT_NAME=$(echo "$ORCH_ARGS" | grep -oE -- '--name [a-zA-Z0-9_-]+' | awk '{print $2}')
```
If `$MAIN_AGENT_NAME` is non-empty, use it directly as `--main-agent-peer-name` below and skip `/rename` entirely — nothing further to set up, and this is what makes reachability survive this main agent's own restart, not just a dispatched agent's. Only fall through to `/rename` when this session was launched with no `--name` at all.

**When no `--name` flag was found, the renamed peer name MUST be unique to this main-agent session, never a bare/unsuffixed literal.** Two concurrent main agents (a scenario `shared-resource-coordination.md` already assumes can happen — "another *main agent's* task can also hit the same port or database") both renaming to the identical literal makes that name resolve to more than one live session. Per `SendMessage`'s own contract, a bare name matching more than one live session doesn't deliver directly — and this project has already recorded a wrong-target `SendMessage` being "reported 'sent' and never seen again, no error anywhere." Now that a dispatched agent's completion push (`notifying-main-agent`'s "Branch: Report your own status") depends on this delivery being real, a shared name isn't just a cosmetic risk — derive a per-session-unique value instead: `<task-name>-orchestrator-<sanitized $HERDR_PANE_ID>`, where `<task-name>` is a short name the main agent picks itself for what this session is actually working on (PascalCase reads fine here — `/rename` isn't run through `check-agent-name.py`'s worker-name regex, confirmed live it accepts mixed case) and the pane-id suffix still guarantees uniqueness the same way (`wF:p9` → `AgentMessaging-orchestrator-wF-p9`). This also makes the session identifiable in `ListAgents` at a glance, not just unique.

Confirmed live: the main agent can make its own peer name deterministic by running `/rename <the unique value>` on itself once — this works even on an already-running session (not just at `claude` launch), takes effect immediately, and is idempotent (renaming to the same name again is harmless). Do this once per main-agent session, before the first dispatch that might need this channel — not per-plan, not per-task. `/rename` does not persist across a session restart, so a freshly restarted main-agent session needs to do this again before it's reachable (and, since `$HERDR_PANE_ID` can change across a restart, may derive a different unique value the next time).

`/rename` is a Claude Code CLI slash command, not a tool call — the main agent cannot trigger it by emitting the text as part of its own response (that only reaches a human-typed input box, not the model's own output). Confirmed live: submit it to your own pane via `herdr agent prompt`, using the pane id `$HERDR_PANE_ID` already exported into the main agent's own environment:
```bash
herdr agent prompt "$HERDR_PANE_ID" "/rename <TaskName>-orchestrator-<sanitized \$HERDR_PANE_ID>"
```
This queues as input for after the current turn (submitting to a `working` pane doesn't interrupt it), so the rename takes effect once this turn ends — no `--wait` needed, and there is nothing further to check for confirmation until the *next* turn (`herdr agent get "$HERDR_PANE_ID"`'s `terminal_title` will read the renamed value once it has).

**No `$HERDR_PANE_ID` at all (herdr fully unavailable to this main agent).** `/rename` can only be injected via `herdr agent prompt` into the main agent's own pane, so a main agent with no herdr pane has no way to rename itself at all — it's stuck with Claude Code's own auto-derived peer name, which (per "SendMessage peer name" above) it also cannot look up. This is a pre-existing gap this capability doesn't attempt to close; it only matters for `claude-p`-only dispatch under a main agent that itself has no herdr, a narrower case than the concurrent-main-agents scenario this fix targets.

**The dispatch instruction must also state the dispatched agent's own instruction path** — `get-main-agent.py`, `report-progress.py`, and `report-task-status.py --instruction-path` all require it, and the agent has no other way to know it. It's computable *before* calling `dispatch-task.py write` (whose `--task` argument is this very prompt, so its own return value isn't available yet to quote): `app` and `--slug` are chosen by the caller, not returned by the script, so the path is deterministically `<home>/.straw-boss/dispatch/<app>--<slug>.json` — resolve `<home>` the documented way (`python3 -c "from pathlib import Path; print(Path.home() / '.straw-boss')"`, never a literal `~/...`), same as `dispatch-mechanics.md`'s "Resolving the home directory" already requires for every other command that touches this path.

**What the dispatch instruction states, per kind/mode:**
- Claude `herdr-pane`: instruction path, main-agent pane id, exact `SendMessage` peer name, the provider-neutral progress/status commands, and the `notifying-main-agent` requirement.
- Claude headless: instruction path, exact peer name, progress/status commands, and the fire-and-forget `notifying-main-agent` requirement.
- Codex `herdr-pane`: instruction path, main-agent pane id, exact `report-progress.py`/`report-task-status.py` commands, and the `awaiting-*` rules. Never cite the unavailable Claude skill or `SendMessage`.
- Codex headless: instruction path and the exact progress/status commands. Its confirmed thread id is recorded after launch and is the continuation identity for `codex exec resume`.

Pass `$HERDR_PANE_ID` for any `herdr-pane` dispatch. `--main-agent-peer-name` is required only for Claude; omit it for Codex. This keeps provider-neutral Plan correctness independent of a Claude mailbox identity while preserving Claude's existing guaranteed-addressing check.

## Self-compact (main agent compacting its own context)

The main agent can compact itself the exact same way it injects `/rename` above — `herdr agent prompt` typing a slash command into its own pane isn't limited to `/rename`; `/compact` works identically:
```bash
herdr agent prompt "$HERDR_PANE_ID" "/compact <optional focus text>"
```
This is the main agent's own judgment call, not a fixed schedule. Per the `/rename` note above, this queues as input for after the current turn — it never interrupts work already in flight this turn. The real question is what the *next* turn would need that exists only in this turn's working context and isn't written down anywhere durable yet (`plan.json`, an instruction file, a status/artifact write) — compacting loses whatever that is. Reach for it once that's settled: between plan waves, after a batch of dispatches lands, not while state the next turn needs still exists only in this turn's own reasoning. No `$HERDR_PANE_ID` at all (herdr fully unavailable) means this channel doesn't exist for this main agent — Claude Code's own automatic compaction as context fills is the only fallback, same as for any session.

## Making an agent addressable

`herdr agent start`'s trailing `-- --name <name>` flag (passed through to the underlying `claude` process, distinct from herdr's own `<unique-name>` control handle that's the command's first argument) sets the exact name that shows up in `ListAgents`/is reachable via `SendMessage`, overriding the auto-derived `<cwd-basename>-<suffix>` default entirely. `dispatch-mechanics.md`'s `herdr agent start` command already passes the same value for both — no separate naming decision needed here.

**Build `<unique-name>` as `<this main agent's own task-name>-<worker-slug>`** — the same `<task-name>` this main agent already picked for its own peer name above (dropping the `-orchestrator-<pane-id>` suffix, which exists only to make the *orchestrator* unique, not to identify it), plus the `--slug` already chosen for this dispatch's `dispatch-task.py write` call. This ties a worker back to its dispatching main agent at a glance in `ListAgents` (`AgentMessaging-fix-replay` next to `AgentMessaging-orchestrator-wF-p9`), unlike a bare `plan_id`/`task_id` slug alone. `check-agent-name.py`'s regex accepts mixed case (`^[A-Za-z][A-Za-z0-9_-]{0,31}$`), so the task-name segment doesn't need lowercasing — but it does still count against the 32-character total, so keep both segments short.

## Inform

Send a dispatched agent an FYI about something the main agent discovered, without interrupting its current turn. Confirmed live via the `/rename` bootstrap above: `herdr agent prompt "<name>" "<message>"` **without** `send-keys esc` first, sent to a `working` pane, queues as input for after the current turn ends rather than interrupting it — the pane keeps working uninterrupted and picks the message up once it's naturally free.

```bash
herdr agent prompt "<name>" "[from main agent] <informational message>"
```

No `--wait` — the agent is still `working` on its current turn, so `--wait` would match that unrelated turn finishing, not acknowledgment of this message. This action never changes the agent's terminal status.

**Not available for `claude-p`.** A headless one-shot process has no live pane to queue input into — there's nothing to inform mid-run. Use `notifying-main-agent`'s own reverse-direction channel (agent → main agent) for that direction instead; there's no main-agent → `claude-p` equivalent.

## Redirect

Confirmed live: `herdr agent send-keys "<name>" esc` interrupts a currently-`working` turn and drops the agent back to `idle`, ready for a new prompt — matches Claude Code's own interactive Escape-to-interrupt behavior. Use this when the main agent learns of an urgent requirement change mid-task (from the user, typically, or from its own autonomous judgment per `docs/roles.md`'s autonomy boundary) and the task itself is still right but needs adjusting before it finishes its current turn, rather than waiting for it to finish first:

```bash
herdr agent send-keys "<name>" esc
herdr agent prompt "<name>" "<corrected instruction, stating what changed and why>" --wait --timeout <ms>
```

Confirm the interrupt actually landed (`herdr agent get "<name>"` reports `idle`, not still `working`) before sending the correction — sending a new prompt while the prior turn is still finishing queues behind it rather than replacing it.

**`claude-p` cannot be interrupted mid-flight.** There is no live process to send a key to once it's running — the only options are to let it finish and redispatch with corrected instructions afterward, or `TaskStop` the background task outright (discarding whatever it was mid-way through) and redispatch fresh — the latter is mechanically the same action as Cancel below, just followed by a fresh dispatch instead of recording `cancelled`. If a task dispatched as `claude-p` seems likely to need a mid-task correction, that's itself a reason to have used `herdr-pane` instead — see `dispatching-work`'s Task 1 mode-selection criteria.

## Cancel

End a dispatched task outright because the main agent judges the dispatch itself — not the agent's execution of it — was wrong (wrong app, wrong scope, superseded by new information). Unlike Redirect, there's no corrected instruction to send; the task is simply over.

**`herdr-pane`:** interrupt, then close without expecting further output:
```bash
herdr agent send-keys "<name>" esc
herdr pane close <pane_id>   # + herdr tab close <tab_id> if it was the last pane in it, + git worktree remove if full-flow
```
Then call `report-task-status.py --instruction-path <path> --status cancelled --note "<why the dispatch itself was wrong>"` yourself — same script every dispatched task uses to report on itself (plan or standalone, per `dispatch-mechanics.md`'s "Reporting scripts"), just invoked by the main agent this one time, since the agent never sees this happen and can't report it. `--instruction-path` resolves to the right file either way (a plan task's existing status file, or a standalone dispatch's own `.status.json`) — never hand-write the status JSON.

**`claude-p`:** `TaskStop` the backgrounded process — the same mechanism Redirect above already uses to abort an undeliverable correction, repurposed here to end the dispatch instead of redispatching fresh:
```bash
TaskStop  # on the backgrounded claude-p task's id
```
Then call `report-task-status.py --instruction-path <path> --status cancelled` yourself, same as the `herdr-pane` case above. Discards whatever the process was mid-way through either way; there is no partial-output recovery.

**Cancelling a task other tasks `depends_on` strands them — decide their fate at cancel time, don't leave it implicit.** `read-plan-status.py`'s ready-wave computation only treats a prerequisite as satisfied when it's `done`; `cancelled` (like `failed`) never satisfies a dependent, so a dependent of a cancelled task sits `planned` forever — never ready, never in-flight, but also never terminal, so the plan can never complete. A `failed` prerequisite arrives through the status watcher; a `cancelled` one is authored by the main agent inline, so the same main-agent action must immediately inspect its dependents. Cancel them too or re-dispatch the prerequisite under a corrected spec — never leave them queued against a prerequisite that will not arrive.
