## 1. Live verification (must land before anything below is written as fact)

- [x] 1.1 Run `codex exec --json "echo hi"` (or equivalent trivial prompt) once; identify the exact JSONL field that carries the session/thread id. → `thread_id` in the first `{"type":"thread.started",...}` event.
- [x] 1.2 Start a real herdr pane, run `herdr agent start <name> --kind codex --pane <id> -- ` (interactive codex, no prompt yet), then `herdr agent get <name>`; confirm whether a session-identifying field equivalent to claude's `agent_session.value` is present. Record the finding either way. → absent at start, populated (`agent_session`, same shape as claude's) only after the first real `herdr agent prompt`.
- [x] 1.3 Confirm the first-run trust/onboarding behavior for a fresh codex pane (does it block the way claude's first-run trust prompt does, per dispatch-mechanics.md step 5's `blocked` check?) and whether `herdr agent wait --until idle,blocked` behaves the same for `--kind codex`. → yes, same `blocked` shape, cleared with `send-keys enter`; `--until` must be repeated per value on this herdr version, comma form errors (affects the existing claude section too, see 4.4.1).
- [x] 1.4 Run `claude --help` and enumerate the actual `--permission-mode` value list, to fill out design.md's ordinal mapping's claude-side column completely. → `acceptEdits`, `auto`, `bypassPermissions`, `manual`, `dontAsk`, `plan`.
- [x] 1.5 If 1.1-1.4 surface a fact that changes design.md's Decisions (not just fills in an Open Question), update design.md before continuing. → done (Decisions 3 and 4 updated with full mapping and confirmed session-id behavior).

## 2. Config schema

- [x] 2.1 Add optional `agentKind` field (string, default `"claude"`) to the `apps.json` schema in `skills/init/references/apps-config-schema.md`, documented alongside `forbidDirectCommit` in the field reference table.
- [x] 2.2 Update `init`'s `SKILL.md` to ask, per app, whether it should default to a non-`claude` agent kind (optional, skippable, defaults to `claude`).
- [x] 2.3 Add a separate, project-wide (asked once, not per app) `init` question: enable one or more additional agent kinds beyond `claude`? Loop to allow configuring a second and a third if the user wants more than one, per spec's "Setup offers to configure more than one additional agent kind." → new Task 3 in `init`'s `SKILL.md` (existing Tasks 3-9 renumbered to 4-10).
- [x] 2.4 For each additional agent kind the user enables, ask what kind of work should route to it, then recommend a model/reasoning-effort — check for an existing local preference first (that agent CLI's own config file, e.g. `~/.codex/config.toml`'s `model`/`model_reasoning_effort`; a relevant installed plugin skill's own routing rule, e.g. `codex:codex-cli-runtime`; the user's personal root `CLAUDE.md` if it already has a routing table for that kind) and only fall back to a fresh web search when none of those give a clear answer for the work type described. Present the recommendation and get explicit confirmation or an override before recording anything, per spec's "Recommended model/effort is grounded in existing preference."
- [x] 2.5 Write the confirmed routing decision(s) into the project's root `CLAUDE.md` as a new prose section (which kind of work → which agent kind/model/effort), not into `apps.json`, per spec's "Agent-kind routing policy is recorded as project-wide prose." → dedicated `<!-- straw-boss:agent-routing:start/end -->` marker pair.

## 3. `dispatch-task.py`

- [x] 3.1 Add `--agent-kind` (default `"claude"`, script-level default so omitting it is a no-op behavior change) to the `write` subcommand; the caller still resolves the actual value from `apps.json`/root-`CLAUDE.md` policy/explicit override before invoking the script.
- [x] 3.2 Record `agent_kind` on the instruction file payload (`write_instruction`). Verified live: `agent_kind`/`agent_model`/`agent_effort` all land in the written JSON.
- [x] 3.3 Refuse (raise `ValueError`) when `--agent-kind` is anything other than `claude` and `--plan`/`--task-id` are also given — enforces the spec's "Non-claude dispatch is restricted to standalone tasks" requirement at the tooling layer. Verified live: `--agent-kind codex --plan fake-plan --task-id t1` refuses before touching any plan file.
- [x] 3.4 Add `--observed-session-id` (optional) to the `confirm` subcommand; when given, overwrite the instruction's `session_id` with this value instead of asserting it matches what `write` generated (used for kinds that can't pre-assign a session id, per design.md Decision 4). Verified live.
- [x] 3.5 Reject an unrecognized `--agent-kind` value up front (a fixed set: `claude`, `codex` for this change) — enforces the spec's "Unresolvable agent kind is refused" requirement. Verified live: `--agent-kind bogus` refuses before any file is written.
- [x] 3.6 Add optional, unenforced `--agent-model`/`--agent-effort` to `write` (and record on the instruction payload); populated only when the main agent's own root-`CLAUDE.md` routing-policy judgment led it to override the agent kind's own default, per design.md Decision 7 — purely for traceability, not validated against any fixed value set.

## 4. `dispatch-mechanics.md`

- [x] 4.1 Add a "Resolving the agent kind" section: app default → per-dispatch override → `claude` fallback, mirroring how `<app_dir>` resolution is already documented.
- [x] 4.2 Add the permission-mode ordinal mapping table from design.md Decision 3 (claude modes / codex-headless flags / codex-herdr-pane flags), corrected per task 1.4's findings.
- [x] 4.3 Add a `codex exec` headless dispatch section, parallel to the existing `claude -p` section, including how the session id is read back from the `--json` event stream (per task 1.1's finding), with `-m <agent_model>`/`-c model_reasoning_effort=<agent_effort>` spelled out explicitly on the command line (post-review fix — an earlier draft only folded them into the sandbox/approval-flags placeholder, which resolves to permission flags only and never actually carries model/effort).
- [x] 4.4 Add a `codex`-kind herdr-pane dispatch section, parallel to the existing steps 1-8 (split into its own "steps 4-8" section after extracting the agent-kind-agnostic pane-setup steps 0-3 into a shared section) — covers the real first-run trust prompt, `--source visible` for reading a blocked pane, no `--name`/`SendMessage` addressability, `agent_session` only appearing after the first real prompt, and the same explicit `-m`/`-c model_reasoning_effort=` fix as 4.3.
- [x] 4.4.1 Fixed the claude-only `herdr-pane` section's `herdr agent wait --until idle,blocked` to the repeated-flag form. Post-review: the same bug also existed in `skills/init/SKILL.md`'s Task 9 (bootstrap-completion wait) — a second occurrence missed on the first pass, found by re-grepping `--until` repo-wide and fixed the same way.
- [x] 4.5 Note explicitly, near the top of the file, that agent kind and `mode` are orthogonal — a reader must not assume `claude-p`/`herdr-pane` implies `claude`.

## 5. `dispatching-work` skill

- [x] 5.1 Task 1 (renamed "Choose the dispatch mode and agent kind"): notes transport (mode) and agent kind are resolved independently — state both before dispatching.
- [x] 5.2 Task 3/4: reference the new `--agent-kind`/`--agent-model`/`--agent-effort`/`--observed-session-id` flags where the existing text describes `dispatch-task.py write`/`confirm`; Task 4's permission-mirroring note now points at the per-kind mapping table instead of a single flag string.
- [x] 5.3 Added a Red Flag: app's configured agent kind is codex, dispatch a plan/batch task under it directly — no, force to `claude` and state why.
- [x] 5.4 Post-review addition, not in the original task list: `skills/boss-say/SKILL.md` Task 1's execution-tier criterion still said "needs the app's own skills/hooks/rules to actually load," which now disagrees with `docs/architecture.md`'s widened "needs the app's real working directory" tier definition (task 6.2). Reworded to the same "real working directory" criterion, noting skills/hooks/rules loading is specifically the `claude`-kind case.

## 6. Docs

- [x] 6.1 `docs/roles.md`: reworded "Dispatched agent" so "does the actual work against the app's real harness (skills/hooks/rules)" is stated as true for `claude`-kind dispatches specifically, not dispatched agents in general.
- [x] 6.2 `docs/architecture.md`: same reframing in the tier-definition prose, the transport paragraph, and the `dispatching-work`/`init` Components-table rows.

## 7. Validation

- [x] 7.1 `openspec validate --changes multi-agent-dispatch --strict` — passed. `python3 -m py_compile scripts/dispatch-task.py` — compiles clean.
- [x] 7.2 Covered by the live verifications already performed rather than re-running a duplicate full pass: Task 1's herdr+codex pane test exercised the real sequence end-to-end (start → trust prompt cleared → prompt submitted → transcript confirmed → `agent_session` read back → pane closed), and Task 3's `dispatch-task.py` smoke test exercised `write --agent-kind codex --agent-model gpt-5.6-sol --agent-effort high` and `confirm --observed-session-id <real uuid>`, both landing correctly in the instruction file's JSON. Re-running the same sequence a second time end-to-end would verify nothing new.
- [x] 7.3 Confirmed in Task 3's smoke test step 1: `write` with no `--agent-kind` given still produces `agent_kind: "claude"`, `agent_model: null`, `agent_effort: null` — unchanged behavior for an unmodified caller.
