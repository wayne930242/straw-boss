# Shared-resource coordination (cross-main-agent)

Worktree isolation solves *file* collisions between tasks. It solves nothing about a fixed network port a dev server binds to by default, or a database multiple tasks verify migrations against — both live outside any one checkout. Worse, this collision isn't even limited to one main agent's own fleet: a main agent has no visibility into what *another*, independently running main-agent session has dispatched, so `dispatching-work`'s own bookkeeping can't catch it. This file covers both cases through one mechanism (`scripts/claim-resource.py`) — a per-resource lock that also doubles as the live record of who currently holds what.

**Scope: same machine, same user only.** `~/.straw-boss/locks/` is per-machine state, same as every other `~/.straw-boss/` directory — it coordinates multiple main-agent sessions running under one user account on one machine (e.g. several herdr workspaces open at once). It does **not** protect against a different machine or a different user's session hitting the same shared DB or exposed port — that would need a lock the shared resource itself enforces (a lock table in the DB, a reservation service), which is out of scope here.

**Every call below is one command — never hand-write a retry/wait loop in the dispatch instruction.** `wait` and `claim-port` already loop internally (bounded, with progress printed to stderr); the only place a raw bash loop would add anything is if the caller needed external visibility into each poll, which a single dispatched task's own private wait doesn't.

## Ports — try a deterministic candidate first, always lock whatever you land on

Every port a worktree's dev server actually binds to gets locked, no exceptions — the difference between the two port cases below is only how the candidate port is chosen and what happens on contention, not whether it gets locked. This is also what satisfies "record which port is assigned to which worker": the lock file for `port--<app>--<port-number>` **is** that record (see "Visibility" below), and locking even a freely-chosen port means two tasks that independently land on the same number are caught by the lock instead of racing at bind time.

**Flexible (the app's dev-server port is configurable).** The dispatch instruction tells the agent to run this once, right before starting the dev server:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" claim-port \
  --app "<app>" --key "<worktree absolute path>" --holder "<app>--<slug>" \
  --requester-boss "<this dispatch's main-agent pane id or SendMessage peer name>" --note "dev server for <slug>"
```

It derives a starting candidate from `--key` (`hashlib.sha256`, not the randomized `hash()` builtin — that's why this lives in the script rather than a one-off shell one-liner) within `--base`/`--range` (default `3000`/`500`), then acquires it, incrementing on contention up to `--max-attempts` (default 5, never unbounded) before giving up.

**Set `--base`/`--range` deliberately, at instruction-assembly time — the defaults are not safe to leave unexamined.** The lock only prevents two *worktrees* from landing on the same port; it does nothing to keep the derived range from overlapping the app's own default dev-server port, its HMR/websocket port, or a sibling service's fixed port. Check what the target app actually uses before picking a range, and choose one that doesn't overlap. Prints the port it landed on in the `port` field of its JSON result — bind the dev server to that, not the app's default. Because the lock is checked *before* binding, this also catches two tasks landing on the identical candidate by hash coincidence, which a bare bind-and-catch-`EADDRINUSE` approach would miss.

**`claim-port` never waits — exhausting `--max-attempts` is a hard failure, by design, not a queue.** A flexible port's whole point is that another number works just as well, so it always prefers moving on over waiting; if every candidate in the derived band is genuinely held, the band is too narrow for how many worktrees are actually running at once — widen `--range` or raise `--max-attempts`, don't add a wait here. Waiting only ever makes sense for the fixed case below, where there's no alternate number to try.

**This is a cooperative lock, not the OS's own accounting — nothing stops a process outside this script from already sitting on a port.** Every `acquire`/`wait`/`claim-port` call on a `port--<app>--<port-number>` resource probes the actual port first (bind-and-immediately-release, IPv4 only) before ever touching the lock file, and treats an externally-occupied port the same as a contended lock (`held_externally: true` in the result — `claim-port` moves to the next candidate, `wait` keeps polling). This is best-effort, not a guarantee: there's an unavoidable gap between this probe and whenever the agent actually binds for real a moment later, so a dispatch instruction that starts a dev server still needs to treat an actual bind failure as a real possibility despite a successful claim — the claim narrows the risk, it doesn't eliminate it.

**The probe can't tell "someone else has it" from "I have it and I'm using it exactly as intended."** Never re-run `acquire`/`wait`/`claim-port` on the same port resource while your own dev server from an earlier successful claim is still bound to it — the probe will see your own listener as an external occupant and report it contended, indistinguishable from real contention. Claim once, run the server, `release` when done; don't loop back through the claim step mid-task.

**Fixed (the port value itself is externally constrained — hardcoded app config, or another service's CORS allowlist expects an exact origin/port, even if the dev-server tool itself could technically bind elsewhere).** There is no alternate candidate to try — incrementing would just break CORS again. This is the agent's actual **request** for that exact port: it uses `wait` on `port--<app>--<port-number>` exactly like the DB case below, and if it's taken, waits rather than substitutes.

## Shared DB migrations — always the lock

A shared, stateful database can't be isolated by a formula the way a port can. Any task that runs or verifies a migration against a database that isn't per-worktree (a shared staging/dev DB) uses the lock, `resource: "db-migration--<db-identity>"` — `<db-identity>` is whatever stably names the actual shared target (host+dbname, or the app+env pair the migration runs against).

**`--resource` becomes a filename, and must stay portable to Windows** — only `A-Za-z0-9._-` (`claim-resource.py` rejects anything else). Use `--` as the separator between parts, never `:`.

## The lock protocol

`holder` is the dispatch instruction's own filename stem, `<app>--<slug>` — already known at instruction-assembly time, and lets anyone reading a lock file cross-reference `~/.straw-boss/dispatch/<app>--<slug>.json` for full detail without a separate identity scheme. Pass `--requester-boss "<this dispatch's main-agent pane id or SendMessage peer name>"` on every `acquire`/`wait`/`claim-port` too (from the same reachability info the instruction already carries for `notifying-boss`) — it's what makes the "courtesy channel between main agents" below possible; skip it and a stuck waiter's main agent has no way to know who to ask.

**This runs inside the agent's own task, not the main agent.** The main agent doesn't pre-acquire before dispatch or babysit the wait — it only decides which case applies (Task 4 of `dispatching-work`/`shipping-task`, when assembling the instruction) and writes the exact `--resource`/`--app`/`--key` values and the relevant command into the dispatch instruction. The agent claims right before it actually needs the resource (starting the dev server, running the migration) — never earlier, so a long implementation phase before that point never holds the lock uselessly against other main agents' unrelated work.

**`--ttl-seconds` is a crash-recovery timeout, not a work-duration budget — set it well above the expected duration of the work it guards, deliberately, at instruction-assembly time.** It exists only so a lock survives a main agent/agent that crashes or gets killed without releasing; it is not a queueing fairness mechanism, and there is no renewal. A task still legitimately working when its TTL lapses gets its lock silently reclaimed by the next waiter — the main agent states a realistic number, not the `1800` default by reflex, when it knows this task's migration/verification normally runs longer.

**The claiming task is told this, not left to remember its own `--ttl-seconds` flag.** Every successful `acquire`/`wait`/`claim-port` echoes `ttl_seconds` back in its own JSON result, plus a `note_to_holder` spelling out that it's reclaimable after that long without a release — the dispatch instruction doesn't need to separately remind the agent, the tool's own output does.

The DB case, and the fixed-port case, both use `wait`:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" wait \
  --resource "db-migration--<db-identity>" --holder "<app>--<slug>" \
  --requester-boss "<this dispatch's main-agent pane id or SendMessage peer name>" \
  --ttl-seconds 1800 --note "<short reason>"
# ... run the migration / start the dev server here ...
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" release \
  --resource "db-migration--<db-identity>" --holder "<app>--<slug>"
```

(For the fixed-port case, `--resource "port--<app>--<fixed-port-number>"` instead.) **Leave `--max-wait-seconds` unset — that's what guarantees a resource can never stay stuck forever.** With it unset, `wait` never gives up before whatever `--ttl-seconds` the *current holder* actually declared has elapsed — recomputed fresh on every poll, so it tracks the real holder even if a different one grabs the lock in between. Once that elapses, the very next poll reclaims it. Passing an explicit `--max-wait-seconds` doesn't change that guarantee for anyone else — it only makes *this* call give up sooner than the holder's own ttl, on purpose, when a task would genuinely rather fail fast and let a human decide than keep waiting. Don't add it as a matter of habit.

**Always invoke the script with the full `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py"` form**, same as every other script in this plugin — it is not executable on its own and a bare `claim-resource.py ...` call fails.

**`reclaimed_stale: true` in an acquire/wait/claim-port result proves the previous holder outlived its own TTL — it does not prove the previous holder is dead.** It could be a crashed/abandoned task, or it could be a task genuinely still running past a TTL that was set too tight. Before touching a shared DB on the strength of a reclaimed lock, check whether the previous holder's own dispatch instruction still exists and is `in-progress`: `~/.straw-boss/dispatch/<held_by>.json` (the `held_by` value the earlier contended attempt reported). Archived/wrapped-up (or the file is simply gone) is a real "it finished" signal, safe to proceed on. Still `in-progress` means genuine uncertainty — surface it to the user rather than proceeding, and don't run a migration against a database another live session might be mid-migration on.

**`--force` on `release` overrides the holder check — use it deliberately, never by default.** Only reach for `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" release --resource <id> --holder <id> --force` after `status` shows the lock's `age_seconds` well past its `ttl_seconds` (a live holder never needs to be forced out) or after confirming with the user that the recorded holder is actually dead.

## Visibility — what's assigned right now

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" list --prefix "port--"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" list --prefix "db-migration--"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" status --resource "<specific resource id>"
```

`list` is the live registry of every currently held lock — `resource`, `holder`, `holder_boss`, `age_seconds`, `expired`. This is the answer to "which port is currently assigned to which worker": read it, don't maintain a separate tracking file, and don't assume a resource is free just because no task in *this* main agent's own plan claimed it — `list` covers every main agent on the machine.

**A stale lock that nobody ever re-contends for just sits there — `acquire`'s reactive reclaim only fires when someone actually asks.** That's not a correctness problem (`expired: true` in `list`/`status` already tells the truth about it, and it can never block anything that isn't itself contending for that exact resource), but it can clutter the picture over time. Run `uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" gc` occasionally to sweep every lock already past its own `ttl_seconds` regardless of contention — it never touches anything still within its ttl, so it can't remove a live lock by mistake.

## Courtesy channel between main agents

The lock is what actually enforces correctness — everything here is optional, and never changes who wins a contended claim. It exists because a stuck waiter finding out *who* holds a lock (via `held_by_boss` on a contended result, or `holder_boss` in `list`/`status`) can do something with that beyond just polling blind.

**One stuck waiter, one current holder.** The waiting main agent reaches the holder's main agent directly — same fire-and-forget, informational-only pattern as `notifying-boss` (`herdr agent prompt`/`SendMessage`, self-identified, never awaited for a reply): asking for a rough ETA, never asking it to force-release or treating any reply as authorization to skip the lock. The lock's own `ttl_seconds` is still the only real arbiter — a "sure, go ahead" reply from another main agent doesn't override it; only an actual `release` does.

**Several main agents contending on the same resource around the same time.** The lock records only the current holder, not the waiters — there's no roster to broadcast to. It resolves without one: every waiter's `held_by_boss` names the *same* main agent (the current holder's), so that holder's main agent is the one that naturally accumulates however many "any ETA?" pings arrive from different waiters in the same window, making it — not any waiter — the one that actually knows the full set of interested parties. If it gets more than one, it proposes an order back to whoever asked, then stops. No new role, no file, no "current coordinator" record — this ends the moment that round of replies is sent, and a proposed order is only ever a suggestion: each waiting task still has to win `acquire`/`wait` like anyone else once its turn comes.
