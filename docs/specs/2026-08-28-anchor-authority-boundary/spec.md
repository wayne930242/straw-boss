# Anchor authority boundary specification

## Observable behavior

- `docs/roles.md` states both halves of the boundary in one place: the main
  agent names which anchor proves a task and arranges its checkpoint, including
  any shared resource that must exist before the worker has anything to show;
  the user and dispatched agent choose the method inside that anchor.
- Every surface that grants the worker a verification method scopes that grant
  to the reality anchor — the contract `dispatch_state.render_dispatch_contract`
  actually builds, `docs/roles.md`, `CONTEXT.md`, `skills/i-am-orchestrator`,
  `plan-mechanics.md`'s brief rule, `boss-say`, `dispatching-work`,
  `shipping-task`, and `bringing-coworker`.
- The testing anchor's default is unit tests at the smallest credible seam that
  can go red before the change; the **worker** escalates to integration or E2E
  when the target project's own conventions call for it.
- A coordination graph is selected on an observable criterion: how many
  app-rooted workers run under one coordination loop, and by what mechanism.
  - `single-loop` — one agent end to end; a coordinator driving a single
    dispatch's lifecycle, or a worker that brought one coworker, is this shape.
  - `sub-agent fan-out/fan-in` — subagents through the working agent's own
    `Agent` tool.
  - `orchestrator-worker` — more than one app-rooted worker under one status
    loop. A confirmed dependency graph and a capped batch are both this shape.
    It is the only graph that writes `~/.straw-boss/plans/<slug>/plan.json`.
- The anchor's own check, including an independent review agent, is not a branch
  of the work and never changes the graph.
- The human anchor covers an artifact the user **operates**. Reading code or a
  document is review; with nothing to operate, the anchor is the independent
  agent's adversarial review.
- Adversarial review accompanies every ordinary programming change and **can**
  serve as the anchor when the other three offer no checkpoint.
- The anchor set is closed at four, and `docs/roles.md`, `choosing-graph`,
  `docs/architecture.md`, and both READMEs name the same four.
- Read-only work has no artifact to operate and no change to go red, so its
  anchor is adversarial-review. What that independent agent attacks is the
  report's claims against the evidence references `inspecting-app`,
  `investigating-app`, and `troubleshooting-app` already require; those
  references make the attack possible rather than being the anchor. Both
  read-only skills say so in their own deliverable paragraph.

  Superseded on 2026-08-28 by `docs/specs/2026-08-28-close-rereview-findings/`:
  the rule reaches `troubleshooting-app`'s integration preflight rather than the
  whole skill, and that skill's other branch takes the testing anchor.
- A frontend human/pseudo-human anchor has its port claimed by the main agent at
  dispatch, with `--ttl-seconds` set against the whole task's lifetime.
- The worker binds that number and never re-runs the claim, because the lock is
  keyed on the port number with no holder identity: a second `claim-port` from
  the same holder reads its own live lock as contention and walks to the next
  candidate.
- A dispatch-time claim is released on every terminal status through every path
  — `dispatching-work`'s Wrap-up branch for a standalone dispatch, its plan
  auto-detach for a batch item or plan task. `done` is not an exception.

## Vocabulary

`CONTEXT.md` registers **coordination graph**, **reality anchor**, and
**team-mode / solo-mode**, each with the terms it retires.
