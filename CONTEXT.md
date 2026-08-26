# straw-boss

Who the actors are in a straw-boss-orchestrated workflow, how they're named, and who decides what. The canonical language every skill's prose is built on — resolved during the 2026-08-19 roles/authority grilling session (see `docs/adr/`).

## Language

### Cast

**User**:
The human who hands work to straw-boss and gives direction. The actual "boss" per the plugin's own ranch-foreman naming metaphor (README: "跟牛仔一起在現場做事，不是坐辦公室發號施令").
_Avoid_: boss (in prose describing the orchestrating session)

**Main agent**:
The orchestrating Claude Code session — the "straw-boss"/foreman itself. Triages scale and execution tier, dispatches work, never touches app code directly. The canonical term used in skill prose.
_Avoid_: boss (in any identifier — skill name, script name, field name)

**Dispatched agent**:
A session `dispatching-work` spawns, rooted in a target app's own directory, running through `herdr-pane` or `claude-p`. Does the actual work against the app's real harness (skills/hooks/rules).
_Avoid_: worker (fine informally, but "dispatched agent" is canonical in prose), agent (too generic alone)

**Subagent**:
An ephemeral `Agent`-tool call for self-contained work that doesn't need the target app's own harness. No app-dir rooting; `dispatching-work` is never invoked for one.

### Naming convention

**"boss" (identifier rule)**:
In any identifier — skill name, script name, JSON field, CLI flag — "boss" refers only to the user, never to the main agent. `boss-say` is correctly named (the user speaks, the plugin acts). `notifying-boss` was misnamed (it's a dispatched agent notifying the *main agent*, not the user) — renamed to `notifying-main-agent`.

### Authority — actions on in-flight dispatched work

**Inform**:
The main agent sends a dispatched agent an FYI with `send-dispatch-message.py --to worker --intent inform`. The script validates the recorded live session and queues the message without interrupting the current turn. Not available for `claude-p`.

**Redirect**:
The main agent interrupts a dispatched agent mid-task to correct or change its instruction, because the task itself is still right but needs adjustment. After the lifecycle controller interrupts the recorded pane, `send-dispatch-message.py --to worker --intent redirect` delivers the correction. `herdr-pane` only.
_Avoid_: interrupt (alone — always pair with what happens after: a redirect, not a cancel)

**Cancel**:
The main agent ends a dispatched task outright because it judges the dispatch itself was wrong (wrong app, wrong scope, superseded) — distinct from the dispatched agent's own work failing. Ends in the `cancelled` status, never `done`/`failed`, so `boss-say`'s failure reporting and `plan-mechanics.md`'s failed-task redispatch-ask-the-user flow (which is about the *agent's own* failures) aren't corrupted by a main-agent-initiated stop. `herdr-pane`: interrupt (`send-keys esc`) then close pane/tab/worktree without expecting further output. `claude-p`: `TaskStop` on the backgrounded process — the same mechanism already used to abort a `claude-p` task for a redirect that can't be delivered live, repurposed here to end it and record `cancelled` instead of redispatching fresh.

Inform/redirect/cancel are all main-agent-initiated, one direction only. The other direction — a dispatched agent's own outcome reaching the main agent — is untouched by any of this: a task that fails on its own still reports `failed` through its status file the same way it always has (`plan-mechanics.md`'s Monitor notification), and whether to redispatch it is still always the user's call, never the main agent's, exactly as before this authority framework existed.

Work-detail discussion and authorization go directly between an interactive dispatched agent and the user. The main agent relays only for headless tasks, or answers integrated instructions, cross-task context, and coordinator-owned actions.

### Autonomy boundary

The main agent may, on its own judgment — without asking the user first, but always stated, never silent — adjust an item's spec or add work at two levels: (a) items not yet dispatched, (b) in-flight dispatch-instruction files for already-running tasks (via **inform** or **redirect**, or a **cancel** if the dispatch itself was wrong). It may not silently authorize a merge, or a push landing outside a task's own feature branch, or bypass `forbidDirectCommit` under this authority — those gates are absolute, never a function of scope. Pushing a task's own feature branch is not one of these gates — it needs no authorization to begin with. The same restraint covers tracker-ticket mutations: a dispatched agent never touches a ticket; only the main agent does, once the relevant work is actually complete. It defers to the user, rather than acting alone, whenever an adjustment would diverge substantially from the user's stated direction.
