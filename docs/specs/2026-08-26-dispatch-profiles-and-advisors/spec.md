# Dispatch profiles and advisors specification

## Observable contract

### Initialization and routing policy

- `init` asks once per project whether the user wants work-type dispatch routes.
- For each route it obtains:
  - the work description used for matching;
  - worker `agent kind` (`claude` or `codex`);
  - optional provider profile;
  - optional model and effort overrides;
  - for Claude only, an optional native advisor model.
- Before recommending any value, `init` checks the provider's local config,
  applicable personal instructions, and installed provider-specific routing
  guidance. It uses current official guidance only when local evidence gives no
  clear preference.
- The entire route is presented for confirmation or override before it is
  written between the existing `straw-boss:agent-routing` markers in root
  `CLAUDE.md`.
- A later `init` run presents existing routes and lets the user keep, edit,
  remove, or add routes without silently replacing them.
- Dispatch resolution order is: explicit one-off route/profile override, a
  matching project work route, app-level `agentKind`, then Claude with provider
  defaults. The main agent states the resolved worker and advisor with its
  reason before writing an instruction.
- The main agent resolves only the app, work route, dependency/resource facts,
  and dispatch mechanics. It does not inspect target implementation, precedent,
  or tests merely to enrich the brief.
- The brief carries the user requirement, requested outcome, necessary hints and
  constraints, exact supplied artifact references, and verified coordination
  facts already known. The worker discovers target-app context in its own
  directory and harness.
- If coordination or integration needs target-app problem investigation or
  current-state research, the main agent dispatches that research into the app
  rather than reading across managed app roots.
- Investigation, audit, and diagnosis briefs ask for behavior, mechanism, cause,
  or impact with evidence references. They are not yes-or-no existence checks.
- A bounded investigation can resolve to a confirmed lower-tier route such as
  Haiku or a lower-tier Codex model; the route never weakens the evidence
  obligation.

### Dispatch instruction

- `dispatch-task.py write` accepts and records optional `--agent-profile` and
  `--advisor-model` values in addition to agent kind/model/effort.
- `--advisor-model` with an agent kind other than `claude` is rejected before
  any instruction is written. Omitting it means no advisor override.
- The instruction shape is:

  ```json
  {
    "agent_kind": "claude",
    "agent_profile": "worker",
    "agent_model": "sonnet",
    "agent_effort": null,
    "advisor_model": "opus"
  }
  ```

- Missing `agent_profile` and `advisor_model` fields are treated as `null` for
  older instructions.

### Provider launch adapter

- `launch-dispatched-agent.py` is the authoritative interactive provider-argument
  adapter. It derives launch arguments from the instruction:

  | Field | Claude | Codex |
  |---|---|---|
  | provider profile | `--agent <value>` | `--profile <value>` |
  | model | `--model <value>` | `--model <value>` |
  | effort | `--effort <value>` | `-c model_reasoning_effort=<value>` |
  | advisor model | `--advisor <value>` | unsupported |

- Contract injection, session identity, and permission arguments retain their
  current behavior.
- Raw `--agent-arg` remains available for provider options not owned by the
  instruction schema. A caller that also supplies profile/model/effort/advisor
  through raw arguments receives an actionable duplicate-owned-option error.
- Headless mechanics translate the same recorded fields with the same mapping.
  The Claude example includes `--agent`, `--model`, `--effort`, and `--advisor`;
  the Codex example includes `--profile`, `--model`, and reasoning effort.
- Provider CLI rejection of an unknown model/profile/effort/advisor is returned
  as a launch failure; Straw Boss does not silently substitute another value.

### Native advisor behavior

- Advisor is a Claude Code launch setting, not a Straw Boss lifecycle role.
- For a Claude instruction with `advisor_model`, the launch adapter adds
  `--advisor <model>` to the same process as the primary worker model.
- Claude Code owns advisor compatibility checks and decides when to consult it.
  A provider launch error remains visible and the dispatch is not silently
  downgraded to a session without the requested advisor.
- Codex instructions cannot record an advisor. Straw Boss does not substitute a
  coworker, Codex profile, or second dispatch.
- Existing worker-owned coworker behavior is independent and unchanged.

## Compatibility and failure behavior

- Existing app configs, routing prose, instruction JSON, generic coworker calls,
  and dispatches without advisor/profile fields remain valid.
- Existing explicit agent-kind and model/effort CLI arguments remain accepted.
- Existing arbitrary raw launch arguments remain accepted except when they
  conflict with a newly instruction-owned option.
- Claude and Codex remain the only supported agent kinds until a provider launch
  and permission adapter exists for another kind.
- Claude Code's advisor works in interactive and `-p` launches when the
  installed CLI, account, API route, feature flag, and model pairing accept it.

## Non-goals

- No automatic choice is made from task text inside a Python script; route
  matching remains the main agent's policy judgment.
- No advisor transcript or decision is routed through the main agent.
- No model catalog, provider API, or cost optimizer is introduced.

## Correctness strategy

Standard-library integration tests exercise public CLIs with temporary dispatch
state and fake Herdr:

1. `dispatch-task.py write` records worker profile and Claude advisor, and
   rejects Codex advisor before writing a file.
2. Fake-Herdr argv capture proves Claude and Codex receive instruction-owned
   profile/model/effort exactly once, and Claude receives advisor exactly once.
3. Old instructions remain compatible and generic coworkers remain unchanged.
4. Source-contract tests prove `init` and `dispatching-work` describe one
   route/profile flow while `bringing-coworker` does not claim advisor behavior.
5. Source-contract tests prove dispatching, shipping, batch planning, role docs,
   and the immutable worker contract leave target-app discovery to the worker.
6. Source-contract tests prove managed-app investigation/audit/diagnosis always
   dispatch, permit confirmed lower-tier routes, and demand explanatory evidence
   rather than binary answers.
7. The focused lifecycle suite, full unit suite, Python compilation, strict
   OpenSpec validation, and contradiction scans complete verification.

## Applied standards and evidence

- `CONTEXT.md` and `docs/roles.md`: main agent owns route/launch mechanics.
- `docs/specs/2026-08-25-dispatched-agent-lifecycle-transport/`: one launch
  adapter and immutable instruction/receipt identity.
- `openspec/specs/agent-kind-dispatch/spec.md`: explicit confirmation of local
  model preference and project-wide routing prose.
- Installed `claude --help` and `codex --help`, checked 2026-08-26: provider
  profile, model, and effort flag mappings.
- Anthropic's Claude Code advisor documentation, checked 2026-08-26:
  `--advisor <model>` is a per-session setting, Sonnet + Opus is a documented
  common pairing, and Claude decides when to consult it.
- Workspace `AGENTS.md`: read-before-write, TDD, scoped changes, and relevant
  verification.

## Human appropriateness

No later checkpoint is required. The user confirmed the route-centric workflow
and corrected the advisor boundary before implementation.

## User confirmation

Confirmed on 2026-08-26, including that native advisor is Claude Code-only and
Codex does not support it.
