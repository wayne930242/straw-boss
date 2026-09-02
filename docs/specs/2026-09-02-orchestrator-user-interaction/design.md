# Design

## Approach

Define the interaction rule once in the execution-time authority source and
carry the actionable stance into the SessionStart-injected orchestrator skill.
Update only the existing batch and headless-checkpoint branches that actually
present a main-agent-owned user decision. Add focused text-contract tests around
those seams.

## Affected interfaces

- `docs/roles.md`: authority-level contract for compact coordination reports and
  sequential user decisions.
- `skills/i-am-orchestrator/SKILL.md`: executable main-agent stance injected by
  `scripts/orchestrator-priming.py`.
- `skills/boss-say/SKILL.md`: batch mode and plan confirmation decisions.
- `skills/dispatching-work/SKILL.md`: main-agent handling of headless user-input
  checkpoints.
- `skills/dispatching-work/references/plan-mechanics.md`: provider-neutral
  checkpoint mechanics used by the dispatch lifecycle.
- `scripts/launch-dispatched-agent.py`: pre-dispatch shared-tab naming and
  post-split worker-pane naming.
- `scripts/run-headless-dispatched-agent.py`: executable Codex thread capture
  and checkpoint resume for the existing headless route.
- `tests/test_skill_instruction_quality.py` and
  `tests/test_dispatched_agent_lifecycle_contract.py`: source and injected-body
  contract coverage.

## Existing precedent

- `docs/roles.md` is already the single execution-time authority source.
- `skills/i-am-orchestrator/SKILL.md` already limits worker communication to
  coordination deltas and is injected verbatim, without frontmatter, at
  SessionStart.
- `boss-say` already treats the batch mode as one batch-wide decision and asks
  item ambiguity individually.
- `plan-mechanics.md` already separates interactive direct answering from
  headless relay.

## Decisions and trade-offs

- Use the provider-neutral phrase “harness-native ask-question interface.” This
  covers Claude and Codex without encoding a tool name unavailable in the other
  harness.
- “One decision” is the unit, not one field or one option. Indivisible judgment
  remains one prompt; independent judgments are serialized.
- Keep ordinary reports compact without imposing a word count. A fixed limit
  would compete with the context needed to identify a task or failure.
- Keep direct interactive worker questions unchanged. The sequential-question
  rule applies when the main agent itself presents a user-owned decision.
- Follow provider capability for headless answers: Codex resumes its recorded
  thread through the headless runner; Claude reports terminal `failed`, keeps
  its worktree, and is redispatched with the answer.
- Preserve a one-question plain-text fallback when the active harness exposes no
  ask-question interface.
- Rename the coordinator tab before splitting the worker pane, then rename the
  worker pane after the final agent name succeeds. Retry each once; retain the
  task delivery path if Herdr still rejects a label and return the warning in
  the existing launch result.

## Risks

- Repeating the full rule in every branch would inflate prompt prominence and
  drift. Branch text therefore points to the concrete action only where the
  main agent actually asks.
- “One question” could accidentally split one coherent confirmation into
  fragments. The contract uses one user-owned decision as the boundary.
- Existing tests normalize prose heavily; focused assertions must test both the
  source stance and the body actually emitted by the priming hook.
- Concrete batch or checkpoint branches can override the compact top-level
  stance. Conflict assertions cover pane routing, provider continuation, and
  unchanged-status reporting.

## Reality-anchor method

Run the focused skill-quality and lifecycle-contract suites. Then inspect the
complete diff as a fresh-context adversarial review against the approved five
requirements, with special attention to batched questions and unchanged worker
authority.
