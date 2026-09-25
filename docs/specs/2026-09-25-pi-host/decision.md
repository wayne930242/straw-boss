# Pi host support

Outcome: a Pi main session runs Straw Boss routing, planning, and git lifecycle entirely inside Pi, dispatching app-rooted Pi workers through `pi-herdr-agents`.
Actors: the user, the Pi main agent, Pi workers launched by `subagent`, and the existing Claude Code, Codex CLI, and Antigravity hosts whose behavior stays unchanged.

## Existing mechanisms

- Straw Boss skills route through [boss-say](../../../skills/boss-say/SKILL.md), [work-on](../../../skills/work-on/SKILL.md), [choosing-graph](../../../skills/choosing-graph/SKILL.md), [shipping-task](../../../skills/shipping-task/SKILL.md), and [reporting-to-user](../../../skills/reporting-to-user/SKILL.md); launch, status, and cleanup live in [dispatching-work](../../../skills/dispatching-work/SKILL.md) and its Python scripts, which depend on Claude/Codex/Antigravity hooks, transcripts, and session fingerprints.
- `pi-herdr-agents` provides `subagent`, automatic `subagent_result` delivery, `caller_ping` with `subagent_resume`, stall notices, and optional Herdr worktrees.
- `weihung-user-claude` already carries Pi ports of Straw Boss pieces: `pi/extensions/dispatch-recovery.ts` with `scripts/pi-dispatch.py` (`dispatch_control` roll-call, reattach, handoff over a per-session ledger), `pi/extensions/pane-balance.ts`, and `pi/skills/{shipping-task,dispatch-recovery,orchestrator-handoff}`, with tests under its `tests/`.
- Codex and Antigravity already resolve `${CLAUDE_PLUGIN_ROOT}` as the plugin root in skills and hooks.
- The user's Pi `AGENTS.md` defines an active model strategy: named tiers (coding, ui, review, recon, docs, simple, complex_clear, complex_unclear, academic), each with an ordered model list and a thinking level.

## Decisions

| Question | Answer | Basis | Status |
|---|---|---|---|
| Does Straw Boss support Pi as a host? | Yes; Pi is the user's primary main-agent host. | User reply on 2026-09-25 ("yes"). | confirmed |
| Is Pi a supported public host of this repository? | Yes. | User reply on 2026-09-25 ("no problem"). | confirmed |
| Which dispatch path does a Pi host use? | Entirely inside Pi: Pi main agent, Pi workers, `pi-herdr-agents` dispatch. A Pi host launches no Claude, Codex, or Antigravity worker, and those hosts launch no Pi worker. | User reply on 2026-09-25. | confirmed |
| Where do the Pi dispatch mechanics live? | In Straw Boss: `dispatch-recovery.ts`, `pi-dispatch.py`, `pane-balance.ts`, and their tests move here; `weihung-user-claude` keeps personal configuration and installs Straw Boss as a Pi package. They live under `pi/`, apart from the Claude/Codex/Antigravity `scripts/`. The three Pi skills there are replaced by Straw Boss skills. | User answer to Q1 on 2026-09-25. | confirmed |
| Do Claude Code, Codex CLI, and Antigravity hosts change? | No; their manifests, scripts, hooks, and skill text outside the Pi branches keep their behavior. | Q1 option "agree" keeps those paths; the freeze option was declined. | confirmed |
| How does a Pi worker obtain a user decision outside its granted authorizations? | It calls `caller_ping` with the question, options, and a recommendation, then ends its turn; the main agent gathers all pending decisions, asks them together through `ask_user`, and continues the worker with `subagent_resume`. | User answer to Q2 on 2026-09-25. | confirmed |
| How is a Pi worker's model chosen? | By tier from the user's active Pi model strategy: the full model list and thinking level of that tier. A project work route on Pi names a tier only. | User answer to Q3 on 2026-09-25. | confirmed |
| How are multi-task dependencies and progress recorded on Pi? | Launched dispatches live in the `dispatch_control` ledger; undispatched tasks and dependency edges live in the main agent's todo list; each `subagent_result` triggers the next scheduling round. No `plan.json`, status directory, or watcher. | User answer to Q4 on 2026-09-25. | confirmed |
| Which features does the first Pi version include? | Core only: `boss-say`, `work-on`, `choosing-graph`, `shipping-task`, `reporting-to-user`, `dispatching-work` (Pi branch), and `dispatch_control`. | User answer to Q5 on 2026-09-25. | confirmed |
| Are the shared-resource locks carried to Pi? | No. | User message on 2026-09-25 ("no need for the complicated Straw Boss locks"). | confirmed |
| Does a Pi host run Straw Boss scripts? | No. The Pi branch keeps the workflow (route, resolve, graph and anchor, lifecycle mode and mutation checkpoints, review, report) and carries it out with Pi tools, plain git, and direct reads of `apps.json`. Only the moved Pi extension and its own helper run code. | User message on 2026-09-25 ("Pi native basically uses no Straw Boss scripts; the core focus is keeping the workflow"). | confirmed |
| How does a team-mode Pi worker get its worktree? | The main agent creates and verifies it with the plain-git commands of [Worktree ownership](../../../skills/dispatching-work/references/plan-mechanics.md#worktree-ownership), copies declared `localFiles` with plain file copies under the same rules (a missing required entry stops the launch, sensitive entries need user authorization, contents are never printed), then launches `subagent` with that path as `cwd`. | `subagent`'s own `worktree` option launches the worker immediately, leaving no point to copy `localFiles`; no Straw Boss script runs on Pi. | grounded |
| Where does Pi-specific skill text live? | In a separate Pi skill set under `pi/skills/` with the same six names; the skills under `skills/` stay byte-identical for Claude Code, Codex, and Antigravity. Policy shared by both sets is guarded by tests: `reporting-to-user` stays identical, and graph names, anchor categories, and lifecycle modes match. | User message on 2026-09-25 ("make sure boss-say and the dispatch skills cannot break the Claude and Codex systems; writing two sets of skills is fine if needed"); the live smoke test showed a Pi agent misreading host-specific steps in a shared skill. | confirmed |
| Do in-flight Pi dispatches survive the move? | Yes; the moved extension keeps the ledger, handoff, and delivery directories under the Pi agent directory. | Ledger paths are derived from `PI_CODING_AGENT_DIR`, not the package path. | grounded |

Core rules readiness: routing authority stays in `skills/i-am-orchestrator/SKILL.md` and `skills/boss-say/SKILL.md`; app configuration in `skills/init/references/apps-config-schema.md`; no open decision remains.
