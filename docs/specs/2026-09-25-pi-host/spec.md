Status: approved
Approved at: 2026-09-25
Approved from: the user's reply on 2026-09-25 ("implement")

# Pi host support

Decisions: [decision.md](decision.md).

## Observable behavior

### Package

1. `package.json` at the repository root declares a `pi` manifest. `pi install <straw-boss checkout or git source>` loads exactly these resources:
   - skills `boss-say`, `work-on`, `choosing-graph`, `shipping-task`, `reporting-to-user`, `dispatching-work`, from the Pi set under `pi/skills/`;
   - extensions `pi/extensions/dispatch-recovery.ts` and `pi/extensions/pane-balance.ts`.
2. `pi/scripts/pi-dispatch.py` is the dispatch-recovery helper; it and both extensions keep the behavior they have in `weihung-user-claude`, including the ledger, handoff, forwarded, and delivered directories under the Pi agent directory.
3. The Claude Code and Codex plugin manifests, `hooks/`, `scripts/`, and every host's behavior outside the Pi branches are unchanged.

### Pi main-agent workflow

The Pi branch runs no file under `scripts/`.

4. **Route.** `boss-say` on Pi selects the owning skill, resolves targets through `work-on`, names the graph and reality anchor through `choosing-graph`, and resolves source-changing items' lifecycle mode through `shipping-task`, exactly as on other hosts.
5. **Resolve.** `work-on` on Pi reads `.straw-boss/apps.json`, else `.claude/straw-boss/apps.json`, directly from the git root, applying the same location, error, implicit-app, match, redirect, and `crossAppSkills` rules.
6. **Worker setup.** The main agent picks a tier from the user's active Pi model strategy (a project work route on Pi names a tier; otherwise the task's nature decides, `coding` by default) and passes that tier's full model list and thinking level to `subagent`.
7. **Checkout.** Solo-mode and read-only work launch with the app directory as `cwd`. Team-mode work launches in a worktree the main agent created and verified with plain git, after copying declared `localFiles`: a missing non-optional entry stops that launch and reports its path and note; a sensitive entry is copied only under user authorization; file contents are never printed.
8. **Brief.** Each `subagent` task (English) carries the work, the anchor and who exercises it, its place and motive, the carried authorizations, and the Pi worker contract: ask for any decision outside those authorizations with `caller_ping` (question, options, recommendation), and end with a final message giving the completion reference (commit, MR/PR, merge), evidence references, and review disposition.
9. **Schedule.** Every task is a todo item. Undispatched tasks record their dependency edges in the todo. Ready tasks launch in the same turn up to the concurrency cap (the invocation's cap, else 4). Each `subagent_result` starts one scheduling round.
10. **Events.**
    - `subagent_result` success: confirm the completion reference and review disposition per `choosing-graph`'s review checkpoint, remove a main-created worktree with `git worktree remove`, check off the todo, then launch newly ready dependents.
    - `subagent_result` failure: dependents stay blocked; the main agent reports them and resolves the next action with the user.
    - `caller_ping`: the main agent collects every pending decision, asks them together through `ask_user`, and continues each worker with `subagent_resume` carrying the answer.
    - stall notice: reported to the user with the worker's pane.
11. **Mutation checkpoints.** `shipping-task`'s rules hold: commits, the task's own feature-branch push, and MR/PR creation continue within the lifecycle; merge and pushes to other branches require user authorization, which a Pi worker requests through `caller_ping` unless the brief already carries it.
12. **Recovery and handoff.** `dispatch_control` `roll-call` lists this session's dispatches, `reattach` resumes a stopped worker, and `handoff` transfers the scope; the handoff summary includes undispatched tasks and dependency edges from the todo.
13. **Close-out.** Finished work is reported through `reporting-to-user`, and accepted Next items enter one new `boss-say` round.

### Migration

14. `weihung-user-claude` installs Straw Boss as a Pi package, removes its copies of the moved extensions, helper, skills, and tests, and its Pi instructions name the Straw Boss skills.
15. `moldplan-center`'s project `work-on` hands selected tickets, groups, dependency order, and authorizations to `boss-say`, with no harness-specific dispatch mechanics.
16. A Pi session started in `moldplan-center` after installation loads the six Straw Boss skills with no skill name collision.

## Edge cases

- A Pi worker that exits without a completion reference is treated as failed for scheduling.
- A `caller_ping` from one worker while others run does not pause the others; the main agent asks as soon as the pending decisions are gathered.
- A handoff with undispatched dependents carries them only through the summary; the receiver recreates their todo items.
- Pi starting outside a Git repository resolves no apps configuration and uses `work-on`'s implicit-app branch.

## Non-goals

Resource locks and port claims; `plan.json`, status files, and watchers; context renewal and Jev; coworkers; `peeking-work`; orchestrator contact and peer questions; `init` on Pi; cross-host dispatch between Pi and the other hosts.

## Applied standards

- [AGENTS.md](../../../AGENTS.md): skills and docs in English, checked by `tests/test_skill_instruction_quality.py`; suite command `uv run --with pytest pytest -q tests`.
- Host isolation: the Pi set lives in `pi/skills/`; files under `skills/` are unchanged. Tests keep the shared policy aligned between the two sets.

## Reality anchor and checkpoint

- **testing** — the Straw Boss suite plus new tests: the Pi manifest resolves exactly the resources in item 1 through Pi's own resource loader; the moved extension and helper tests pass from their new location; the skill-quality test covers the new text. `weihung-user-claude`'s suite passes after migration.
- **pseudo-human** — in a live Pi session in `moldplan-center`: the loader reports the six skills and zero collisions; `dispatch_control roll-call` answers; one read-only `boss-say` dispatch to a managed app launches a Pi worker and its `subagent_result` returns to the main agent.
- Checkpoint: one fresh-context review of the combined change-set after both anchors pass.
