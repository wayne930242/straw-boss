Status: approved
Approved at: 2026-09-02T11:33:05+08:00
Approved from: user reply "確認"

# Observable contract

1. Main-agent messages to the user contain the current coordination delta and
   the minimum context needed to understand it.
2. A user-owned decision is presented through the harness-native ask-question
   interface available in that session, rather than embedded in a prose status
   report.
3. Each ask-question interaction contains exactly one user-owned decision. When
   multiple decisions are pending, the main agent waits for the current answer
   before presenting the next decision.
4. Each decision prompt includes the smallest context needed to decide and the
   concrete choices or requested judgment; its status preface remains compact.
5. Existing authority stays unchanged: interactive work-detail decisions remain
   in the dispatched worker's pane, while the main agent relays headless
   checkpoints and presents coordinator-owned user gates.
6. Before an interactive dispatch splits its worker pane, it labels the
   coordinator's shared tab with the compact app-derived coordinator identity.
   After it splits the worker pane and resolves the final
   collision-free agent name, it assigns that name to the worker pane before
   submitting the task prompt. Each dispatched worker pane is therefore named
   for the same work identity shown by Herdr's agent list.

## Edge cases

- Closely related fields that form one indivisible judgment may appear in one
  decision prompt. Independent judgments are separate prompts.
- A status update that requires no user decision remains a compact report and
  does not open an ask-question interaction.
- If the current harness has no ask-question interface, the main agent asks one
  concise plain-text question and waits before asking another; this preserves
  sequential decision-making without changing dispatch transport.
- Several workers waiting at once do not justify one multi-decision prompt. The
  main agent identifies the task in each sequential question.
- Headless dispatch has no Herdr worker pane and skips pane naming.
- A coworker reuses its parent worker's tab and does not relabel it.
- Coordinator-tab naming happens before the worker pane split.
- Naming preserves the existing shared-tab layout and coordinator pane.
- A collision retry updates the pane with the final successful agent name.
- A tab- or pane-rename failure is retried. If it still fails, dispatch continues and
  the launcher returns one compact warning with the launch result.

## Compatibility constraints

- Preserve the status-event-driven dispatch lifecycle.
- Preserve direct user interaction in an interactive dispatched pane.
- Preserve the headless `awaiting-user-input` continuation paths.
- Preserve coordination authority and user-gated mutation boundaries.
- Preserve the existing same-tab worker-pane layout.
- Keep `docs/roles.md` as the single execution-time authority source and
  `skills/i-am-orchestrator/SKILL.md` as the SessionStart stance source.

## Non-goals

- Redesigning Plan checkpoints or provider transport.
- Defining product-specific decision choices for dispatched work.
- Adding a new configuration option for report length or question batching.
- Making pane naming a dispatch availability gate.

## Applied standards

- `AGENTS.md`: state expected behavior directly, keep authority and automation
  in their existing artifact classes, and verify before claiming success.
- `leveraging-tasks`: retain this lasting interaction contract and verify every
  requirement separately.
- `writing-great-skills`: put each meaning in one authoritative location, use a
  sharp completion criterion, and avoid duplicate or defensive prompt prose.
- `docs/roles.md`: preserve the established user, main-agent, and dispatched-
  agent authority boundary.

## Evidence and precedent

- `docs/roles.md` defines main-agent authority, direct interactive worker
  questions, and headless relay behavior.
- `skills/i-am-orchestrator/SKILL.md` is injected by
  `scripts/orchestrator-priming.py` into candidate main-agent sessions.
- `skills/boss-say/SKILL.md` already distinguishes one batch-wide mode question
  from item-specific ambiguity and handles user-input checkpoints.
- `skills/dispatching-work/SKILL.md` and
  `skills/dispatching-work/references/plan-mechanics.md` define interactive and
  headless user-input routes.

## Reality anchor and checkpoint

Adversarial review after implementation and focused contract tests. A
fresh-context reviewer checks the finished diff against these six observable
requirements and the repository's authority boundaries. The executable
checkpoint confirms the SessionStart stance contains the compact-report and
one-decision-per-question rules and that relevant checkpoint instructions do not
reintroduce batched user decisions.
