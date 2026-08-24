# Roles & Authority

Who the actors are, how they're named, and who decides what — read this before executing any skill that mentions "main agent," "dispatched agent," "user," or "subagent." This is the single definition; no skill redefines these terms locally.

## Cast

**User** — the human who hands work to straw-boss and gives direction. The actual "boss" per the plugin's own ranch-foreman naming metaphor (the plugin works alongside the crew, it doesn't sit in an office issuing orders).

**Main agent** — the orchestrating Claude Code session, the "straw-boss"/foreman itself. Triages scale and execution tier, dispatches work, never touches app code directly. The canonical term used in skill prose.

**Dispatched agent** — a session `dispatching-work` spawns, rooted in a target app's own directory, running through `herdr-pane` or `claude-p`, under a resolved agent kind (`claude` by default; `dispatching-work`'s own resolution can pick another where the app/task calls for it). A `claude`-kind dispatch uses the app's Claude harness (skills/hooks/rules); a different kind works from the explicit task instruction and the app's own conventions (e.g. `AGENTS.md`). Either kind may participate in a Plan because dependency scheduling consumes provider-neutral status events.

**Subagent** — an ephemeral `Agent`-tool call for self-contained work that doesn't need the target app's own harness. No app-dir rooting; `dispatching-work` is never invoked for one.

## Naming convention

"boss" in any identifier — skill name, script name, JSON field, CLI flag — refers only to the user, never to the main agent. `boss-say` is correctly named: the user speaks, the plugin acts. A name that instead means "notify/reach the main agent" must not use "boss."

## Authority over in-flight dispatched work

The main agent has four distinct ways to act on a task it already dispatched, each with a different blast radius:

**Inform** — send a dispatched agent an FYI about something the main agent discovered, without interrupting its current turn. Mechanically: `herdr agent prompt` (no `send-keys esc`) to a `working` pane — it queues, taking effect only once the agent's current turn ends on its own. Not available for `claude-p` (no live pane to prompt).

**Redirect** — interrupt a dispatched agent mid-task to correct or change its instruction, because the task itself is still right but needs adjustment. Mechanically: `herdr agent send-keys esc` (interrupt) then `herdr agent prompt --wait` (the corrected instruction). `herdr-pane` only.

**Cancel** — end a dispatched task outright because the main agent judges the dispatch itself was wrong (wrong app, wrong scope, superseded) — distinct from the dispatched agent's own work failing. Ends in the `cancelled` status, never `done`/`failed`, so failure reporting and the failed-task redispatch-ask-the-user flow (both about the *agent's own* failures) aren't corrupted by a main-agent-initiated stop. `herdr-pane`: interrupt (`send-keys esc`) then close pane/tab/worktree without expecting further output. `claude-p`: `TaskStop` on the backgrounded process, discarding whatever it was mid-way through — the same mechanism already used to abort an undeliverable redirect, repurposed here to record `cancelled` instead of redispatching fresh.

**Resolve** — answer a dispatched agent's `awaiting-main-agent` checkpoint: an action only the main agent's own judgment or dispatch authority can take, that the agent has stopped and is genuinely waiting on (not mid-turn like Redirect's target, so no interrupt step). Mechanically: `reply-to-worker.py` (`dispatching-work`'s `references/plan-mechanics.md` "Main-agent-action checkpoints") — one atomic call that both delivers the reply and records the resolution. This works for every supported agent kind in `herdr-pane`; a headless Codex continuation uses its recorded thread id with `codex exec resume`.

Inform/redirect/cancel/resolve are all main-agent-initiated, one direction only. The other direction is untouched by any of this: a dispatched agent's own outcome — including a genuine failure — still reports itself, unaffected by the main agent's inform/redirect/cancel authority, and whether to redispatch a failed task is still always the user's call, never the main agent's. Every Plan agent calls the provider-neutral status interface, which writes its record before prompting the recorded main-agent herdr pane; `watch-plan-status.py` emits each transition for recovery and scheduling. `SendMessage` is only a Claude-to-Claude fallback.

A third direction, lateral rather than vertical: one dispatched agent reaching another directly (`asking-peer-agents`), to ask about that peer's own progress or conclusion instead of investigating its app/worktree blind. This carries no authority either way — it's the same informational-only channel `notifying-main-agent`'s question branch already gives a dispatched agent toward its main agent, just addressed sideways instead of up; it never substitutes for inform/redirect/cancel, and a reply through it is never authorization.

## Autonomy boundary

The main agent may, on its own judgment — without asking the user first, but always stated, never silent — adjust an item's spec or add work at two levels: items not yet dispatched, and in-flight dispatch-instruction files for already-running tasks (via inform, redirect, or cancel). It may not silently authorize a merge, or a push landing outside a task's own feature branch (a monorepo-root submodule pointer-bump, an app-owned release push to a protected branch), or bypass `forbidDirectCommit` under this authority — those gates are absolute, never a function of scope. Pushing a task's own feature branch is not one of these gates — it needs no authorization to begin with, so there is nothing for this autonomy to bypass there. The same restraint covers tracker-ticket mutations: a dispatched agent never touches a ticket; only the main agent does, once the relevant work is actually complete. It defers to the user, rather than acting alone, whenever an adjustment would diverge substantially from the user's stated direction.
