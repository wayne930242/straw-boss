## Why

No skill file in this plugin has ever established who the actors are (user vs. main agent vs. dispatched agent vs. subagent), how they're named, or who has authority to act on in-flight work. This is a real, already-observed gap, not a hypothetical one: commit `1c71541` had to reactively rename ambiguous "boss" prose (which meant both "the user" and "the main agent" depending on context) across ~10 files, and `skills/notifying-boss/` carries the exact same ambiguity today at the identifier level, unresolved. Without a positive definition of the cast and naming rules, the plugin's skills lean on scattered "Red Flags" (negation-based patches) to cover gaps a clear upfront architecture would prevent — and there is currently no defined authority for the main agent to act on discoveries about work it already dispatched without stopping to ask the user every time.

## What Changes

- Establish `docs/roles.md` as the single source of truth for the cast of characters, the "boss"-in-identifiers naming rule, and the authority framework. Every skill gets a short context pointer to it instead of restating or re-deriving role prose locally.
- **BREAKING**: rename `skills/notifying-boss/` → `skills/notifying-main-agent/` — its name currently reads as "notify the user" but its actual content is "a dispatched agent notifies the main agent." Every reference to the old name (`shipping-task` Task 4, `docs/architecture.md`, `dispatching-work/references/cross-session-coordination.md`) is updated.
- Introduce a three-tier main-agent authority model over in-flight dispatched work: **inform** (FYI, non-interrupting — the existing non-interrupting `herdr agent prompt` queue behavior, now named and documented as an intentional capability), **redirect** (the existing "Mid-task interrupt and correction" mechanism, now given its canonical name), and **cancel** (new — end a task outright because the dispatch itself, not the worker's execution, was wrong).
- **BREAKING**: add a new `cancelled` terminal status to the dispatch/plan status-file schema (previously only `done`/`failed` were terminal), recognized by `read-plan-status.py`, `wrap-up-task.py`, and the `Monitor` polling guidance in `plan-mechanics.md`. `cancel` is supported for both dispatch modes: `herdr-pane` via interrupt + close, `claude-p` via `TaskStop` on the backgrounded process — the same mechanism `cross-session-coordination.md` already documented for aborting a `claude-p` task that needs an undeliverable live correction, repurposed here rather than built new.
- Define an explicit autonomy boundary for the main agent: it may adjust an item's spec or add work — without asking first, but always stated, never silent — at two levels (items not yet dispatched, and in-flight dispatch-instruction files), via inform/redirect/cancel. This authority never bypasses push/merge authorization or `forbidDirectCommit`, and always yields to the user when an adjustment would diverge substantially from the user's stated direction. A dispatched agent's own failure reporting to the main agent, and the existing rule that redispatching a genuinely failed task is always the user's call, are explicitly preserved and unchanged by this authority.
- Run a mechanical, per-entry audit of every existing "Red Flags" section across all touched skills: fold an entry into `docs/roles.md` as a positive rule (and delete the entry) if it can be phrased positively there; otherwise keep it, paired with the positive target it defends.
- Restructure `docs/architecture.md`'s Components table to point at `docs/roles.md` for role definitions instead of duplicating role prose inline where that duplication currently exists.

## Capabilities

### New Capabilities

- `agent-roles`: the cast of characters (user, main agent, dispatched agent, subagent) and the naming convention that governs how they're referred to in prose and identifiers across the plugin.
- `dispatch-authority`: what the main agent may do to work it has already dispatched — inform, redirect, cancel — the new `cancelled` terminal status this requires, and the autonomy boundary governing when it may act without asking first.

### Modified Capabilities

(none — `openspec/specs/` has no existing tracked capabilities yet; this is the first OpenSpec change in this project)

## Impact

- **Skills**: `boss-say`, `dispatching-work` (+ `references/plan-mechanics.md`, `references/dispatch-mechanics.md`, `references/cross-session-coordination.md`), `work-on`, `shipping-task`, `inspecting-app`, `investigating-app`, `troubleshooting-app`, `notifying-boss` (renamed to `notifying-main-agent`).
- **Docs**: new `docs/roles.md`; `docs/architecture.md`'s Components table restructured.
- **Scripts**: `scripts/read-plan-status.py`, `scripts/wrap-up-task.py` need to recognize `cancelled` as a terminal status alongside `done`/`failed`.
- **External surface**: any automation, prompt, or documentation outside this repo that names `skills/notifying-boss` by path, or assumes only `done`/`failed` are valid terminal status values, needs updating.
