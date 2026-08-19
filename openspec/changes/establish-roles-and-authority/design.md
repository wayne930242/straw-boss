## Context

See `proposal.md` - Why for motivation. Current state that shapes the approach:

- The plugin has no cross-skill shared-doc convention. Existing shared references live either in `docs/` (project-level rationale, e.g. `architecture.md`, explicitly "read this if you're extending the plugin" — not read at execution time) or under a single skill's own `references/` folder that other skills point to by path (e.g. `skills/init/references/apps-config-schema.md`). Neither is a good fit as-is for a doc ~10 skills all depend on equally.
- `skills/dispatching-work/references/cross-session-coordination.md` already implements two of the three authority mechanics informally: `herdr agent prompt` without `send-keys esc` queues behind a working pane without interrupting it (used today only for the `/rename` bootstrap, not named as a general capability), and "Mid-task interrupt and correction" (`send-keys esc` + `herdr agent prompt --wait`) already exists for urgent redirects.
- The plan/status schema (`plan-mechanics.md`) currently has exactly two terminal values, `done` and `failed`, consumed by `read-plan-status.py`, `wrap-up-task.py`, and the `Monitor` polling loop described in `plan-mechanics.md`.
- `boss-say` and other skills carry a long "Red Flags" section each — negation-based patches for behavior a positive definition doesn't currently exist to anchor.
- `CONTEXT.md` and `docs/adr/0001`, `docs/adr/0002` (repo root / `docs/adr/`) already record the resolved terminology and rationale from the grilling session that produced this change; this design translates those into an implementation approach.

## Goals / Non-Goals

**Goals:**
- One authoritative location for role/naming/authority language that every skill points to instead of restating.
- Name and formalize the two authority mechanics that already exist mechanically (inform, redirect) and add the one that doesn't (cancel).
- Fix the `notifying-boss` identifier bug completely, including every reference to it.
- Reduce Red Flags that a positive rule can replace, without blanket-deleting ones that are genuine hard guardrails.

**Non-Goals:**
- Rewriting Red Flags unrelated to roles/naming/authority (e.g. concurrency-cap slicing mechanics in `boss-say`) — only entries whose content is actually about who-decides-what are in scope for the fold-in-or-keep pass.
- Changing anything about `work-on`'s Plan-confirmation gate or `shipping-task`'s push/merge authorization gate — those stay exactly as they are; this change only adds a new, narrower autonomy on top, never loosens them.

## Decisions

**`docs/roles.md`, not a new `skills/_shared/` directory, not scattered per-skill copies.** (`docs/adr/0001`) The reason `architecture.md` currently isn't read at execution time is that no skill points into it as a required read, not that `docs/` is the wrong place for execution-relevant content. Adding a context pointer from each `SKILL.md`'s Overview fixes that without inventing a new top-level convention. Alternative considered: duplicate the cast/naming/authority text into each skill directly — rejected as duplication (10 copies to keep in sync); alternative considered: fold it into `architecture.md` itself — rejected because that file's own framing ("read this if extending the plugin") would keep signaling "background reading," which is the exact failure this change fixes.

**Three named actions — inform, redirect, cancel — not a single generic "main agent can act on in-flight work."** (`docs/adr/0002`) Each has a different blast radius and a different (or absent) existing mechanism, so collapsing them into one undifferentiated "autonomy" concept would hide that distinction from future skill authors. `inform` and `redirect` are renames/formalizations of mechanics that already work; `cancel` is genuinely new.

**`cancelled` is a new terminal status, not `failed` + a note.** Reusing `failed` would conflate two different causes (the worker's own execution went wrong vs. the main agent decided the dispatch itself was wrong) that downstream consumers already treat differently: `boss-say` Task 7's failure summary, and `plan-mechanics.md`'s permission-denial check before asking the user whether to redispatch a `failed` task. A `cancelled` task was never given a chance to fail or succeed on its own merits, so folding it into `failed`'s statistics and its ask-before-redispatch flow would be actively misleading.

**`cancel` is supported for both dispatch modes.** `herdr-pane`: interrupt (`send-keys esc`) then close pane/tab/worktree without expecting further output. `claude-p`: `TaskStop` on the backgrounded process. This was originally scoped to `herdr-pane` only, on the assumption that killing a `claude -p` background process needed new mechanism — revised once implementation found `cross-session-coordination.md`'s existing "Mid-task interrupt and correction" section already documents exactly this: `TaskStop` a backgrounded `claude-p` task, discarding its mid-way progress, as one of two options when it needs a correction it can't receive live. Cancel reuses that same mechanism, recording `cancelled` instead of redispatching fresh — no new capability, only a documented one repurposed and named.

**Red Flags migration is a mechanical per-entry test, not a scope-wide rewrite.** For each existing "Red Flags" entry across the touched skills: if its content can be restated as a positive rule inside `docs/roles.md`, fold it in and delete the entry; if it's a genuine hard guardrail that can't be phrased positively (per this project's own `writing-great-skills` GLOSSARY.md "Negation" entry), keep it, paired with the positive target it defends. This is checkable per-entry, unlike a blanket "trim for verbosity" pass, and avoids deleting guardrails that earned their place (e.g. the batch-refill-immediately and re-peek-throttling Red Flags in `boss-say`, which don't reduce to a cast/naming/authority statement at all).

**`notifying-boss` → `notifying-main-agent` migration is treated as a full rename, not just a directory move.** Every reference by name — `shipping-task` Task 4's dispatch-instruction text, `docs/architecture.md`'s Components table, `cross-session-coordination.md` — is updated in the same change; no reference is left pointing at the old name.

## Risks / Trade-offs

- **[Risk]** A skill author later adds a new role-adjacent term without checking `docs/roles.md` first, reintroducing local ad-hoc definitions. **Mitigation**: the context pointer convention (every `SKILL.md` points to `docs/roles.md` near its top) makes the canonical source easy to find; enforcement beyond that is out of scope for this change.
- **[Risk]** The `cancelled` status change touches scripts (`read-plan-status.py`, `wrap-up-task.py`) that other in-flight plans on a user's machine may be relying on mid-upgrade. **Mitigation**: `cancelled` is additive (a new recognized value, not a change to `done`/`failed` semantics) — an in-flight plan created before this change simply never produces a `cancelled` status until the main agent is upgraded too.
- **[Risk]** `claude-p` cancel via `TaskStop` discards whatever the task was mid-way through with no chance to observe partial progress first, unlike `herdr-pane` cancel where the pane's transcript stays inspectable up to the interrupt. **Mitigation**: this is the same trade-off `cross-session-coordination.md` already accepted for the redirect-that-can't-be-delivered-live case; not a new risk this change introduces.

## Migration Plan

Ordering matters — later steps are expressed in terms of earlier ones:

1. Write `docs/roles.md` from `CONTEXT.md`.
2. Add the context pointer + leading-word usage to every touched `SKILL.md`.
3. Rename `skills/notifying-boss/` → `skills/notifying-main-agent/` and fix every reference.
4. Document `inform`/`redirect` in `cross-session-coordination.md` under their canonical names.
5. Implement `cancel` and the `cancelled` status: schema/script recognition first (`read-plan-status.py`, `wrap-up-task.py`, `Monitor` guidance in `plan-mechanics.md`), then the `herdr-pane` mechanics themselves.
6. Run the Red-Flags mechanical pass across all touched skills.
7. Restructure `docs/architecture.md`'s Components table to point at `docs/roles.md`.

No rollback beyond standard git revert is needed — this is a documentation- and convention-level change plus one additive status value; nothing destructive to existing in-flight state.

## Open Questions

None — every deferrable unknown identified during the grilling session (reference-file location, OpenSpec routing, `claude-p` cancel scope, `cancelled` vs. reusing `failed`) was resolved before this design was written; see `docs/adr/0001` and `docs/adr/0002`.
