# Skill sediment pruning design

## Chosen approach

Treat positive workflow steps and checkable completion criteria as the single
source of truth. Delete defensive mirrors instead of rewriting them. Keep
evidence-backed mechanics near the condition that activates them.

## Affected seams

- `SKILL.md` top level: remove Red Flags and collapse duplicated verification.
- `init` → app reconnaissance: main agent resolves candidate paths; dispatched
  workers inspect app-owned files and return evidence.
- `create-great-harness`: CLAUDE content is the minimal baseline; hook/rule
  branches activate only from evidence or explicit scope.
- `dispatching-work` references: distinguish ordinary Plan waves from capped
  batches, condition moving-base refresh, and let workers discover shared
  resource configuration.
- `peeking-work`: resolve the canonical instruction before reading receipt and
  status artifacts according to their schemas.
- Source-contract tests: assert positive ownership/results and structural
  absence of sediment rather than exact prohibitive sentences.

## Trade-offs and risks

- Shorter skills rely more heavily on checkable completion criteria. Each
  deletion therefore preserves the positive step that changes behavior.
- Removing a guessed hook reduces generic protection but avoids mutating every
  project from an unsupported convention. A concrete project risk can still
  activate the optional hook branch.
- Init reconnaissance adds dispatch overhead, accepted because it preserves the
  app's own agent-system context and returns better evidence.
- Narrowing stale-base handling requires the task author to identify a moving
  base condition; the worker can also detect remote advancement immediately
  before push.

## Verification seam

`tests/test_skill_instruction_quality.py` is the red-capable structural seam.
Existing public-CLI lifecycle tests remain the characterization seam for runtime
behavior. Final inspection repeats the original audit metrics and permits zero
Red Flags sections and zero known contradictions.
