## Why

`dispatching-work` can only ever launch the `claude` CLI — `dispatch-mechanics.md` hardcodes `claude -p` for headless dispatch and `herdr agent start --kind claude` for herdr-pane dispatch, including permission-mode flags (`--permission-mode`, `--dangerously-skip-permissions`) that only exist on `claude`. `herdr integration install codex` has now been run and confirmed (`codex: current (v7)`), so herdr itself can manage a `codex`-kind pane — but nothing in this plugin knows how to launch, mirror permissions onto, or track one. The user wants to be able to dispatch work to `codex` (and, by the same mechanism, other herdr-supported agent kinds later) instead of always assuming `claude`.

## What Changes

- `apps.json` gains an optional `agentKind` field (default `"claude"` when omitted) — a per-app fact, alongside `forbidDirectCommit`, about which agent CLI dispatched work for that app should run under.
- `dispatch-task.py write` gains an `--agent-kind` flag (defaults to the resolved app's `agentKind`, or `"claude"`) and records it on the instruction file — an explicit per-dispatch override the main agent can use without editing `apps.json`.
- `dispatch-mechanics.md` gains a per-agent-kind command table: launch command, permission-mode mapping, and session-id handling for `codex` alongside the existing `claude` rows. `mode` (`claude-p` / `herdr-pane`) stays a transport choice, unchanged in name and meaning — decoupled from which agent CLI runs inside it.
- Permission-mode mirroring gains a per-kind mapping table (main agent's detected mode → the target CLI's own flags) instead of a single command-string swap, since `codex`'s sandbox/approval flags (`--sandbox`, `--ask-for-approval`, `--dangerously-bypass-approvals-and-sandbox`) have no shared vocabulary with `claude`'s `--permission-mode`/`--dangerously-skip-permissions`.
- Session-id handling branches per kind: `claude` keeps pre-assigning a UUID via `--session-id`; `codex` does not accept a caller-supplied id, so its instruction file's `session_id` is filled in from what the launched session actually reports, not asserted equal to something passed in.
- `init` gains a project-wide (not per-app) question: whether to enable one or more additional agent kinds beyond `claude` — plural, a second or even a third is allowed — what kind of work should route to each, and the recommended model/reasoning-effort for each, informed by whatever local preference already exists (an installed agent CLI's own config file, a relevant plugin skill's routing rule, the user's own root `CLAUDE.md` if it already has one) before falling back to a web search. The answer is written as a prose routing-policy section into the project's root `CLAUDE.md` — not a structured per-app config table — which the main agent consults, and states its reasoning against, when it judges whether one dispatch should use a non-default agent kind/model/effort.
- **Scope boundary (v1):** a non-`claude` dispatch is a single, standalone dispatch only — never a plan/batch task. A `codex` agent does not load `.claude/skills/`, so it cannot run `notifying-main-agent`, cannot be reached by name over `SendMessage`/`ListAgents` (no `--name`-equivalent flag exists), and has no built-in way to honor the `done`/`failed`/`awaiting-*` status-file protocol other than being told to write it inline in its own prompt text. Plans, batches, and cross-session coordination remain `claude`-only until a later change addresses them explicitly.

## Capabilities

### New Capabilities

- `agent-kind-dispatch`: dispatching-work can launch a dispatched agent under a configurable agent CLI (`claude`, `codex`, ...) instead of always assuming `claude`, with per-kind launch commands, permission-mode mapping, and session-id handling, scoped to standalone (non-plan, non-batch) dispatches only.

### Modified Capabilities

(none — `agent-roles` and `dispatch-authority`'s existing requirements are about role-definition process and inform/redirect/cancel mechanics, neither of which changes; this proposal only widens what CLI a dispatched agent runs, so no existing requirement's behavior changes.)

## Impact

- `skills/dispatching-work/references/dispatch-mechanics.md` — new per-kind launch/permission/session-id sections.
- `scripts/dispatch-task.py` — new `--agent-kind` flag and instruction-file field.
- `skills/init/references/apps-config-schema.md` — new `agentKind` field documented.
- `skills/init/SKILL.md` — asks about `agentKind` per app during setup (optional, defaults to `claude`), and a separate project-wide question about additional agent kinds, their intended work, and recommended model/effort, written into root `CLAUDE.md`.
- `skills/dispatching-work/SKILL.md` — Task 1/4 note the kind resolution (app default, root-`CLAUDE.md` policy, or explicit override) and the standalone-only scope boundary.
- `skills/boss-say/SKILL.md` — Task 1's execution-tier criterion reworded from "needs the app's skills/hooks/rules" to "needs the app's real working directory," to stay consistent with `docs/architecture.md`'s widened tier definition now that skills/hooks/rules loading is specifically the `claude`-kind case.
- `docs/roles.md`, `docs/architecture.md` — "Dispatched agent" description updated to note that skill/hook loading is a `claude`-kind property, not a property of dispatch itself.
- No change to `capability.json`'s `herdr-enabled`/`claude-p-only` vocabulary or to `mode`'s `claude-p`/`herdr-pane` values — both stay transport-only, orthogonal to agent kind.
