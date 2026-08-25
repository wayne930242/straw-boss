# Clear dispatch instruction design

## Chosen approach

Keep task semantics and lifecycle mechanics in separate prompt layers.

```text
main agent
  -> concise task brief
     -> outcome
     -> verified context and acceptance criteria
     -> task-specific material constraints only

dispatch-task.py write
  -> generated lifecycle contract
     -> communication
     -> checkpoint selection
     -> terminal reporting

target project harness
  -> development method, repository conventions, and enforcement
```

## Affected interfaces

### Task-authoring guidance

`skills/shipping-task/SKILL.md` becomes the canonical authoring rubric. Its
assembly step asks for a clear outcome, sufficient verified context, and only
material task-specific constraints. It explicitly treats possible solutions as
leads and forbids duplicating generic lifecycle prose.

`skills/dispatching-work/references/plan-mechanics.md` applies that same rubric
to Plan tasks while retaining exact cross-task artifact paths as legitimate
required context.

### Generated contract

`scripts/dispatch_state.py:render_dispatch_contract` names the three checkpoint
statuses once. This removes the reason for every specialist to spell their
mechanics out inside the task while preserving durable coordination.

### CLI authoring hint

`dispatch-task.py --task` describes its input as an outcome-oriented brief, not
"full task text". This is guidance only; the script deliberately does not judge
prompt length or vocabulary.

## Trade-offs and risks

- A shorter task can become vague. The rubric therefore removes boilerplate,
  not context: confirmed intent, acceptance criteria, domain facts, and source
  references remain encouraged.
- Some constraints are real. The rubric uses a materiality test rather than a
  blanket ban: verified task-specific constraints remain in the brief.
- Static tests can become prose-coupled. Tests assert the durable authoring
  contract and absence of the old exhaustive checklist, not exact paragraphs or
  word counts.

## Correctness seam

Use standard-library unittest at two public seams: generated contract content
from `dispatch-task.py write`, and the shipped task-authoring source consumed by
the plugin. Both checks can fail before implementation and remain deterministic.
