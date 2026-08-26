# Dispatch profiles and advisors design

## Chosen approach

Extend the existing instruction as the resolved-profile boundary and keep one
provider launch adapter. Model advisor as one optional Claude-only launch field,
separate from the worker-owned coworker lifecycle.

```text
init
  -> confirmed work-type routes in root CLAUDE.md
  -> main agent resolves one route
     -> dispatch-task.py write
        -> primary profile + optional Claude advisor model
        -> launch-dispatched-agent.py
           -> provider-owned argument adapter
           -> Claude/Codex through Herdr
           -> Claude only: attach native advisor to the same session
```

## Domain language and boundaries

- **Agent kind**: executable CLI provider. Current adapters are Claude and Codex.
- **Provider profile**: provider-native named preset, translated only at the
  launch boundary. `_Avoid_: agent type`, because that phrase also describes
  lifecycle roles and Codex subagent roles.
- **Worker**: primary dispatched task owner.
- **Advisor**: Claude Code's native second-model server tool attached to the
  worker session. It is not a coworker or separately dispatched agent.
- **Work route**: project policy mapping a task description to one worker setup.

## Interfaces and data flow

### Routing policy seam

Root `CLAUDE.md` remains prose because route matching is semantic and already
belongs to the main agent. The route shape becomes worker-first rather than
agent-kind-first, allowing multiple routes to reuse a provider with different
models and optional supported advisor settings.

Caller burden: match the task, state the reason, and pass the resolved values.
It does not reconstruct provider CLI flags or investigate target-app content to
pre-compose the worker's context.

### Brief boundary

`dispatching-work` Task 3 is the single operational source for task-brief scope.
The main agent carries user intent and coordination state it already owns; the
worker performs implementation, precedent, and test discovery inside the target
harness. Shipping and batch paths point to this boundary instead of repeating a
research checklist.

When integration is missing a target-app fact, the seam is another dispatched
investigation, not a main-agent read across the app root. That worker loads the
app's agent system, follows an optionally lower-tier confirmed work route, and
returns an explanatory conclusion with evidence references. Binary existence
questions are expanded into the behavior, mechanism, cause, or impact that the
coordinator actually needs to integrate.

### Instruction seam

The primary profile extends existing flat fields with `agent_profile` and
`advisor_model`. The latter is valid only for Claude instructions.
`dispatch-task.py` validates that invariant before writing. Concrete provider
option validity stays at the launch adapter/CLI seam.

### Provider adapter seam

Move profile/model/effort/advisor translation into a small function used by
`launch-dispatched-agent.py`. Two concrete adapters justify the seam:

- Claude: `--agent`, `--model`, `--effort`, and `--advisor`.
- Codex: `--profile`, `--model`, and `model_reasoning_effort`; advisor is
  unsupported.

The function accepts the resolved instruction and remaining raw arguments and
returns one provider argv. Contract and permission arguments stay with the
existing launcher. Its public behavior is verified through fake-Herdr argv.

Deletion test: removing this adapter would redistribute provider flag mapping,
duplicate detection, and instruction application into dispatch skills,
coworker code, and every launch caller.

### Advisor seam

Advisor translation stays inside the Claude provider adapter. It creates no
instruction child, pane, receipt, or status gate. Generic coworker dispatch
remains a distinct collaboration feature.

## Alternatives considered

### Keep arbitrary `--agent-arg`

Rejected as the primary interface. It can launch the desired flags but does not
persist intent, cannot support reliable init policy, and permits the recorded
model to disagree with the actual process.

### Use `agent type` as one provider-neutral field

Rejected. Claude `--agent`, Codex `--profile`, lifecycle roles, and Codex
orchestration agent types have different semantics. `provider profile` is narrow
enough to translate at the launch boundary.

### Emulate advisor with a coworker for Codex

Rejected. A separate session has different context, timing, authority, cost,
and failure behavior from Claude Code's native server tool. Unsupported means a
visible refusal.

### Persist routes as structured `apps.json`

Rejected. Work-type matching is project-wide and semantic, while `apps.json`
stores app resolution and mechanical defaults. Existing agent-kind policy
already establishes root prose as the appropriate boundary.

## Risks and controls

- Provider flags can change. Keep mapping localized and test installed CLI
  help/argv behavior; unknown values fail visibly at provider launch.
- Claude advisor availability depends on account, API route, feature flags, and
  model pairing. The exact requested flag reaches Claude; failure is surfaced
  without fallback.
- Project prose can be ambiguous. `init` writes a canonical route shape and
  dispatch states the chosen route before launch so the user can correct it.
- A brief can be too thin if it drops a material user constraint. Verification
  requires traceability to user direction and known coordination state while
  excluding pre-dispatch target-app research.
- A lower-tier investigator can return an ungrounded binary answer. The brief
  names the explanatory question and evidence obligation, and the coordinator
  integrates only the returned conclusion and references.
- Profile/model/advisor flags could be supplied twice. The adapter recognizes
  owned options and refuses duplicates instead of relying on precedence.

## Verification seam

The public CLIs and fake-Herdr captured argv are the primary red-capable
interfaces. Tests fail before production edits because current instructions lack
`agent_profile`/`advisor_model`, the launcher ignores recorded model/effort, and
Codex advisor requests are not rejected.

No separate human final check remains after specification confirmation.
