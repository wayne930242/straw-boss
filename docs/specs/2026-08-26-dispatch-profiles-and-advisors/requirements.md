# Dispatch profiles and advisors requirements

## Outcome and actors

Straw Boss must learn the user's preferred dispatched-agent setup during
`init`, persist it as project routing policy, and apply the selected provider,
provider profile, model, effort, and optional Claude Code advisor when launching
work. The user confirms preferences. The main agent resolves a route and
launches the worker; Claude Code decides when to consult its configured advisor
inside that session.

## In scope

- Configure routes by kind of work rather than only by additional agent kind.
- Let every route select a worker agent kind, provider profile, model, and
  effort.
- Let a Claude route select one native advisor model.
- Read existing local provider preferences before recommending values and get
  explicit user confirmation before persisting them.
- Persist confirmed routes as project-wide prose in root `CLAUDE.md`.
- Resolve and state the complete worker/advisor profile before each dispatch.
- Record the resolved profile in the dispatch instruction.
- Make the launch adapter apply recorded profile/model/effort/advisor instead of
  relying on a caller to duplicate them as raw provider arguments.
- Reject advisor configuration for Codex or another provider without an advisor
  launch adapter.
- Keep dispatch briefs to user requirements, necessary hints/constraints, and
  already-known coordination facts; let workers discover target-app context.
- When integration needs target-app problem investigation or current-state
  research, dispatch it into that app instead of reading across managed app
  roots from the main-agent session.
- Allow bounded investigation routes to use a confirmed lower-tier model while
  requiring an explanatory conclusion with traceable evidence.

## Out of scope

- Hard-coding Codex for documentation or Sonnet/Opus for programming in every
  project. Those are recommendations/preferences confirmed during `init`.
- Emulating advisor behavior with a Codex coworker or subagent.
- Replacing app-level `agentKind`, explicit per-dispatch overrides, Herdr, or
  headless transport.
- Inventing a provider-neutral catalog of available model/profile names. The
  selected provider CLI remains authoritative for accepted values.
- Controlling when Claude Code consults its advisor; that timing is model-driven.

## Scenarios

1. During `init`, the user chooses documentation work, confirms a Codex worker
   profile, and declines an advisor. Later documentation dispatches use that
   route without asking the same preference again.
2. During `init`, the user chooses programming work, confirms a Claude Sonnet
   worker and a Claude Opus advisor. A matching dispatch records both and
   launches one Claude Code session with `--model sonnet --advisor opus`.
3. A route uses a named Claude agent profile; launch translates it to
   `claude --agent`. A Codex route uses a named config profile; launch translates
   it to `codex --profile`.
4. A dispatch explicitly overrides one route selection without modifying the
   persisted policy used by later dispatches.
5. A recorded model differs from the provider's local default; the actual
   launch arguments contain the recorded model and effort.
6. A Codex route attempts to set an advisor; instruction writing refuses before
   creating a dispatch rather than emulating the feature.
7. An old instruction has no profile or advisor fields; it launches and reports
   exactly as before.
8. A generic coworker is requested; the existing review-only/file-disjoint
   coworker flow remains independent and unchanged.
9. The main agent can route a code task from its stated target and constraints;
   it dispatches without first researching implementation context. The worker's
   own investigation supplies the fuller, harness-local context.
10. Integration needs to understand a managed app's current behavior. The main
    agent dispatches an investigation rather than reading the app, and the
    worker returns how the behavior works plus evidence references rather than a
    yes-or-no result.
11. A bounded research route uses a user-confirmed lower-tier model such as
    Haiku or a lower-tier Codex model; the same evidence obligation applies.

## Confirmed decisions

- The requested capability includes both preference capture and real launch
  application; recording a model without applying it is incomplete.
- Routing is work-type-centric so one agent kind can have multiple model/profile
  combinations and an optional supported advisor.
- `agent kind` means the CLI provider (`claude` or `codex`).
- `provider profile` means a provider-native named preset: Claude `--agent` or
  Codex `--profile`. It is the canonical replacement for the overloaded phrase
  `agent type` in this context.
- `worker` is the dispatched task owner. `advisor` means Claude Code's native
  server tool backed by a second model in the same session; it is not a
  dispatched agent or coworker.
- Root `CLAUDE.md` remains the source of project-wide routing policy; instruction
  JSON records the already-resolved result for traceability and execution.
- User confirmation: 2026-08-26, with the correction that native advisor is
  Claude Code-only and Codex must not emulate it.
- User direction: 2026-08-26; pre-dispatch research to enrich a brief is excluded
  because worker-local discovery is more complete and causes less context
  interference.
- User direction: 2026-08-26; integration research and problem investigation
  also dispatch because reading across project roots loads additional agent
  systems into the coordinator. Bounded investigators may use lower-tier models
  but must answer explanatory questions with evidence, not binary existence
  checks.

## Open questions

None.
