# Close the re-review findings specification

## Observable behavior

- `dispatching-work` Task 3's allowed-source list is the user request, a
  necessary hint or constraint, or an already-known coordination state. The
  anchor is not an item on it; the next clause requires the brief to name the
  anchor it settled on without prescribing the method inside it.
- The generated contract states what a worker does when the dispatch names no
  anchor: ask the main agent to name it. The anchor category stays the
  coordinator's on every path, including the one where the brief omitted it.
- `shared-resource-coordination.md`'s release rule covers both locks that reach
  it — the dispatch-time claim the worker never made, and a lock the worker
  claimed inside its own task and reported without confirming release.
- `dispatching-work`'s Wrap-up branch verifies that every shared-resource lock
  on the instruction is released before `wrap-up-task.py` runs.
- `CONTEXT.md` registers **dispatch shape** — how much work goes out at once —
  as its own term, and no phrase retired by the **coordination graph**,
  **reality anchor**, or **team-mode / solo-mode** entries appears on an
  instruction line under `skills/`.
- `troubleshooting-app` names an anchor on each branch: an independent agent's
  adversarial review of the account for the integration preflight, testing for
  the continuous fix, where the worker's reproduction is what goes red.
- `choosing-graph`'s read-only rule names `troubleshooting-app`'s integration
  preflight rather than the whole skill, and states that its other branch takes
  the testing anchor. This supersedes the `2026-08-28-anchor-authority-boundary`
  bullet that named three skills and then said "both read-only skills".
- When `single-loop` and `sub-agent fan-out/fan-in` both fit, the deciding
  question is whether a branch of the work itself runs in a subagent; if one
  does, the shape is fan-out. The anchor's own check is not such a branch.
- `prose_surfaces()` states why `docs` is scanned non-recursively.

## Records

- `2026-08-28-anchor-authority-boundary/verification.md` reports the red set it
  measured: twelve tests, including the scoping test, with the
  graph-vocabulary test counted once and the lifecycle-vocabulary test named as
  green with its reason.
- The same file's reconciliation note names both earlier specs that record the
  unscoped grant, not one.
- The same directory's `design.md` states that read-only work keeps a mandatory
  adversarial-review anchor and that H's cost was disclosed, not lowered.
