## Context

See `proposal.md` - Why. Current state, confirmed live during this proposal (not assumed from `--help` text alone, per `dispatch-mechanics.md`'s own standard):

- `herdr 0.8.0`: `herdr integration install codex` succeeded, `herdr integration status` reports `codex: current (v7)`. `herdr agent start --help` lists `codex` as a valid `--kind` alongside `claude`.
- `codex-cli 0.147.0` installed. Three relevant invocation shapes, each `--help`-verified:
  - `codex exec [PROMPT]` — non-interactive, one-shot. Flags: `-s/--sandbox {read-only,workspace-write,danger-full-access}`, `--approve-for-me`, `--dangerously-bypass-approvals-and-sandbox`, `--json` (JSONL event stream), `-C/--cd`. **No `-a/--ask-for-approval` flag** and **no `--session-id`/`--name` flag** in this mode.
  - Base interactive `codex` / `codex resume` / `codex fork` — same sandbox flags as `exec`, plus `-a/--ask-for-approval {untrusted,on-request,never}`. `resume`/`fork` take a `[SESSION_ID]` to *resume* a prior session; nothing lets a fresh session pre-assign its own id the way `claude --session-id <uuid>` does.
  - No flag equivalent to claude's `--name` (the flag that makes a claude session addressable via `SendMessage`/`ListAgents`) exists on any codex subcommand.
- `apps.json`, `dispatch-task.py`, and `dispatch-mechanics.md` currently assume exactly one agent CLI (`claude`) throughout — `mode` (`claude-p`/`herdr-pane`) is transport, not agent identity, but no field currently separates the two.
- `claude-p` as a literal string appears in 14 files repo-wide (docs, skills, ADRs) — confirmed via `grep -rl claude-p`.

Additional facts confirmed live during Task 1 of this change's own `tasks.md` (superseding the corresponding Open Questions from the first draft of this document):

- `codex exec --json "<prompt>"` run against a real git repo (no `--skip-git-repo-check` needed there — that flag only mattered for a non-repo scratch directory): the first JSONL line is always `{"type":"thread.started","thread_id":"<uuid>"}`. That `thread_id` is the field to read back as the session id for headless dispatch.
- A benign `{"type":"item.completed","item":{"type":"error","message":"Skill descriptions were shortened..."}}` event appears on a completely successful run — an `item.completed` of `type: "error"` is not by itself proof of dispatch failure; only the absence of a terminal `turn.completed` (or an explicit non-zero exit) should be treated as failure.
- `herdr agent start <name> --kind codex --pane <id>` works exactly as `--kind claude` does. A fresh codex pane hits its own first-run trust prompt ("Do you trust the contents of this directory?") that sets `agent_status: blocked`, identical in shape to claude's — cleared the same way, `herdr agent send-keys <name> enter`.
- Reading a blocked/pre-task codex pane requires `herdr agent read <name> --source visible` — the default `--source recent` returned empty for it (untested whether this also holds for claude; noted here because the codex herdr-pane section needs the working form).
- `agent_session` is **absent** from `herdr agent get`/`agent start`'s result immediately after start, for a codex-kind agent — it only appears after the first real `herdr agent prompt` is sent, populated as `{"agent":"codex","kind":"id","source":"herdr:codex","value":"<uuid>"}`, the same shape as claude's `agent_session`. So the step-7-style session cross-check *does* work for codex, just not until after the first prompt — never at start time.
- `claude --help`'s `--permission-mode` accepts exactly six values: `acceptEdits`, `auto`, `bypassPermissions`, `manual`, `dontAsk`, `plan`.
- Incidental, unrelated finding worth flagging separately (not part of this change's scope, but hit while exercising `herdr agent wait` for the above): this herdr version (0.8.0) rejects a comma-separated `--until idle,blocked` — `--until` must be repeated per value (`--until idle --until blocked`). `dispatch-mechanics.md`'s existing claude-only `herdr-pane` section uses the comma form and is corrected as part of this change's Task 4 edits since the new codex section sits right next to it and both must use the same, actually-working syntax.
- `codex`'s model/reasoning-effort surface, confirmed live: `-m/--model <MODEL>` on every codex subcommand; a config key `model_reasoning_effort` accepted under `-c model_reasoning_effort=<value>`, confirmed recognized (not silently ignored) via `codex --strict-config -c model_reasoning_effort=high ...` exiting clean. This user's own `~/.codex/config.toml` already sets `model = "gpt-5.6-sol"` and `model_reasoning_effort = "high"` as machine-wide defaults — a real, already-expressed local preference, separate from the `codex:codex-cli-runtime` plugin skill's own routing rule ("leave `--model`/`--effort` unset unless the user explicitly requests one") and from this user's personal root `CLAUDE.md` "Cross-Model Consult" section (task-type-conditioned routing, e.g. mechanical tasks → a specific cheap model at low effort, deep review/debugging → high effort with model left unset).

## Goals / Non-Goals

**Goals:**
- Let a dispatch run under `codex` (and, via the same mechanism, any other herdr-supported kind later) instead of always `claude`.
- Let a project configure more than one non-`claude` agent kind — "a second, even a third" — not just a single codex toggle.
- Preserve the existing permission-mirroring invariant ("never more permissive than the main agent's own mode") across agent kinds.
- Zero behavior change for existing apps/dispatches that never opt in.

**Non-Goals:**
- Plan/batch support for non-`claude` kinds (spec's "Non-claude dispatch is restricted to standalone tasks" — deliberately deferred).
- Cross-session coordination (`SendMessage`/`ListAgents` addressability, `notifying-main-agent`) for non-`claude` kinds — no flag exists to support it yet.
- Renaming `mode`'s `claude-p`/`herdr-pane` values or `capability.json`'s `claude-p-only`/`herdr-enabled` vocabulary.
- An exhaustive mapping for every agent kind `herdr agent start --kind` supports (`pi`, `gemini`, `cursor`, ...) — only `claude` and `codex` are mapped; an unmapped kind is refused per the spec's "Unresolvable agent kind is refused" requirement.
- A machine-parsed, per-task-type routing table in `apps.json` (rejected in Decision 7 below — the user explicitly asked for this to live as a prose policy in root `CLAUDE.md` instead, the same place their own personal `CLAUDE.md` already keeps a "Cross-Model Consult" routing table for Codex).

## Decisions

### 1. Config surface: `apps.json` `agentKind` (default `claude`) + per-dispatch `--agent-kind` override
Mirrors `forbidDirectCommit`'s existing pattern — a persistent fact about the app/environment, not a per-task judgment call. `dispatch-task.py write` gains `--agent-kind` (optional; when omitted, resolves from the app's `agentKind`, defaulting to `claude` if that's also unset) and records the resolved value on the instruction file.

*Alternative considered:* let the main agent judge agent kind per task, the way it already judges execution tier. Rejected — agent kind is a capability/compatibility fact (does this app's team standardize on codex, does this app even have `.claude/skills/` worth loading), not a quality judgment that varies task-to-task; re-deriving it every dispatch would be pure overhead with no upside over a stored default.

### 2. `mode` stays transport-only; `agentKind` is a new, orthogonal field
No rename of `claude-p`, `herdr-pane`, or `capability.json`'s `claude-p-only`. `mode` already means "headless one-shot" vs. "live joinable pane" — both concepts map unchanged onto codex (`codex exec` = headless one-shot; interactive `codex` in a herdr pane = live pane).

*Alternative considered:* rename `claude-p` to something agent-neutral (`headless`). More accurate, but the blast radius (14 files, confirmed by grep) is disproportionate to a purely cosmetic gain. Revisit only if the misnomer starts causing real confusion.

### 3. Permission mapping by restriction ordinal, not by literal claude mode string
Rather than hand-mapping every possible `claude --permission-mode` value to a codex flag combo, define a shared 3-tier ordinal and map each side onto it, so "never less restrictive than the main agent's own mode" holds by construction. `claude --permission-mode`'s full value set (confirmed via `claude --help`): `acceptEdits`, `auto`, `bypassPermissions`, `manual`, `dontAsk`, `plan`.

| Ordinal tier | claude modes | codex — headless (`codex exec`) | codex — herdr-pane (interactive) |
|---|---|---|---|
| unrestricted | `bypassPermissions`, `--dangerously-skip-permissions` | `--dangerously-bypass-approvals-and-sandbox` | `--dangerously-bypass-approvals-and-sandbox` |
| guarded-write | `auto`, `acceptEdits`, `dontAsk`, unspecified (CLI default) | `--sandbox workspace-write` | `--sandbox workspace-write --ask-for-approval on-request` |
| read-only | `plan`, `manual` | `--sandbox read-only` | `--sandbox read-only` |

`exec` has no `-a/--ask-for-approval` flag at all (confirmed above) — the guarded-write/read-only rows for headless dispatch rely on `--sandbox` alone, which is sufficient since sandbox mode already blocks writes/execution at the OS level regardless of any approval policy.

`manual` maps to read-only rather than to an attempted "ask for every action" equivalent: that mode's whole point is a human approving each action, and a dispatched agent (headless or fire-and-forget pane) has no live human answering such asks the way the main agent's own session does — treating it as the most restrictive tier is the safe reading, not a guess at an unattended equivalent that doesn't really exist. `dontAsk`'s precise semantics weren't independently confirmed beyond appearing in the value list (`--help` gives no per-mode description) — placed in guarded-write as the conservative middle reading ("skip prompts" without other evidence of being unrestricted); correct this row first if it's ever seen behaving otherwise.

*Alternative considered:* a flat per-claude-mode-string lookup table. Rejected — doesn't generalize to a third agent kind later, where the ordinal scale needs no new claude-side row at all.

### 4. Session-id handling branches by kind
`claude` keeps pre-assigning a UUID via `dispatch-task.py write` and passing it as `--session-id`. `codex` accepts no such flag, so its session id is *read back*, not asserted — confirmed live: for headless dispatch, from `thread_id` in `codex exec --json`'s first JSONL event; for herdr-pane, from `herdr agent get`'s `agent_session.value`, same shape as claude's, but populated only after the first `herdr agent prompt` lands, never at start time — the confirm step for a codex herdr-pane dispatch must send the first prompt before it can read this back, unlike claude where `agent_session` is already meaningful earlier in the sequence. `dispatch-task.py confirm` gains an optional `--observed-session-id` for this record-what-was-reported path, used only when the launch command couldn't pre-assign one.

### 5. Standalone-only scope enforced at the tooling layer, not just documented
`dispatch-task.py write` refuses any `--agent-kind` other than `claude` when `--plan`/`--task-id` are also given — the spec's "Non-claude dispatch is restricted to standalone tasks" requirement is enforced by the script raising, not left as a convention agents are trusted to follow.

### 6. Fit into the existing dispatched-agent machinery rather than a new tier
The existing instruction-file schema, wrap-up, and capability tracking already cover launch/track/close-out, which is most of what's needed. The parts that genuinely don't transfer to `codex` (skill/hook loading, `SendMessage` addressability, plan/batch coordination) are exactly what this proposal scopes out (Non-Goals) rather than trying to shim badly. A dedicated third tier can be designed later if codex dispatch needs to grow into those areas.

### 7. Agent-kind *routing policy* (which work goes to which kind, and its model/effort) lives in root `CLAUDE.md` as prose, not as structured per-app JSON
Per the user's explicit direction: `init` asks, once, project-wide — not per app — whether to enable one or more additional agent kinds, what kind of work should route to each, and the model/effort each should run at. The answer is written into a new section of the project's root `CLAUDE.md` (which `init` already syncs, per `docs/architecture.md`), in the same prose-table shape this user's own personal `CLAUDE.md` already uses for its "Cross-Model Consult" Codex routing — not a machine-parsed rule list in `apps.json`. `apps.json`'s `agentKind` (Decision 1) stays the mechanical, per-app *default* only; the root-`CLAUDE.md` policy is what the main agent reads, at dispatch time, to judge whether *this specific task* should override that default — the same "main agent judges, states the reasoning" pattern `dispatching-work`/`boss-say` already use for mode and execution-tier, not a new mechanism.

**Recommending the model/effort during `init`'s interview:** anchor on what's already real on this machine before inventing a fresh recommendation — confirmed live and available to read: `~/<agent-CLI-home>/config.toml`-style local defaults (this user's own `~/.codex/config.toml` already sets `model_reasoning_effort = "high"` and a specific model), any routing rules already recorded in a relevant installed plugin skill (e.g. `codex:codex-cli-runtime`'s own "leave unset unless asked" rule), and the user's personal root `CLAUDE.md` if it already has a routing table for that agent kind. Only fall back to a fresh web search for current provider-recommended defaults when none of the above gives a clear answer for the work type being configured. Always present the recommendation and let the user confirm or override it before writing anything — never write a silently-chosen default into the project's `CLAUDE.md`.

**Traceability without a new structured config surface:** `dispatch-task.py write`/`confirm` gain optional `--agent-model`/`--agent-effort` (nullable, unenforced) purely to record what the main agent actually chose for a given dispatch — populated only when the main agent's own CLAUDE.md-policy judgment led it to pass `-m`/`-c model_reasoning_effort=` on the codex launch command; left unset (and thus absent from the launch command) means "use that agent kind's own already-configured default," which is itself a reasonable choice, not a gap.

*Alternative considered:* a structured `agentRouting` array in `apps.json` (task-type → kind/model/effort rules), mirroring the CLAUDE.md table's shape in JSON. Rejected per explicit user direction — the policy is meant to live as project-wide prose in `CLAUDE.md`, not per-app structured config, and `dispatching-work` has no existing mechanism that parses task content against a rule table (every other per-dispatch judgment in this plugin — mode, execution tier — is already a main-agent prose judgment, not table-driven).

## Risks / Trade-offs

- **[Risk]** The ordinal permission mapping doesn't perfectly match every claude mode's real semantics → could over- or under-restrict a codex dispatch. **Mitigation:** the mapping always resolves ties toward *more* restrictive, and lives in `dispatch-mechanics.md` as a named, editable table, not buried in script logic — easy to correct without a redesign.
- **[Risk]** codex's session id can't be pre-assigned, breaking the existing "assert equality" cross-check pattern. **Mitigation:** the codex path is "record and report," not "assert" — if the id can't be read back, the dispatch is flagged rather than silently marked confirmed.
- **[Risk]** A codex dispatch has no automatic way to honor the `done`/`failed`/`awaiting-*` status-file protocol (no skill loaded to do it for it). **Mitigation:** covered by the standalone-only scope boundary — a codex dispatch that needs this protocol must have it spelled out inline in its own prompt text, the same way cross-task artifact paths are already inlined for plan dispatches; this is a stated limitation, not solved automatically, and is exactly why plan/batch support is out of scope for v1.
- **[Risk]** `agent_session` for a codex-kind agent isn't populated until after the first prompt — a confirm step written assuming it's readable at start time (like claude's pattern) would fail. **Mitigation:** confirmed live and designed for directly in Decision 4 — the codex herdr-pane confirm sequence reads it back only after sending the first prompt, not before.
- **[Risk]** `dontAsk`'s and `manual`'s exact semantics weren't independently confirmed beyond their names appearing in `claude --help`'s value list. **Mitigation:** both are placed on the conservative side of the ordinal mapping (Decision 3); correcting a specific row later, if either mode is observed behaving differently than assumed, doesn't require touching the mapping mechanism itself.
- **[Risk]** A prose routing policy in `CLAUDE.md` (Decision 7) isn't machine-enforced the way a JSON rule table would be — the main agent could misjudge which task matches which rule, or forget to check the section at all. **Mitigation:** this is the same trust model this plugin already places in the main agent for mode and execution-tier judgments; `dispatching-work`'s Task 1 states its resolved agent kind and reasoning before dispatching (task 5.1), so a misjudgment is visible and correctable in the moment, not silent.

## Migration Plan

Purely additive — `agentKind` defaults to `claude`, `--agent-kind` defaults to the resolved app default, and the root-`CLAUDE.md` agent-routing section is only written if the user opts into a second/third agent kind during `init`. Every existing app, instruction file, and `CLAUDE.md` keeps working unchanged with zero config changes required. No data migration: an existing instruction file simply lacks the new fields, which anything reading it treats as `claude`/unset. Rollback is a plain revert — nothing new depends on the fields or the `CLAUDE.md` section existing.

## Open Questions

None remaining — Task 1's live verification (see Context) resolved the session/thread-id field, the `herdr agent get` session-field question, and the full `claude --permission-mode` enum, all folded into the Decisions above.
