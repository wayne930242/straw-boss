# Dispatch mechanics

Exact file formats and command sequences for `dispatching-work`. Everything below reflects what was actually verified against `herdr` v0.8.0 and the installed `claude` CLI — not assumed from general knowledge. If a `herdr`/`claude` upgrade changes any of this, re-verify rather than trusting this file blindly.

All state lives under a `.straw-boss/` directory in the user's home directory, not the target project's checkout — this is per-user, per-machine operational state (which dispatch mode this user prefers, what's currently dispatched), not project configuration.

## Resolving the app directory — never assume `apps/<app>`

`<app_dir>` below always means `<repo_root>/<dir>`, where `<dir>` is the resolved app's `apps.json` entry (`skills/init/references/apps-config-schema.md`) — or `<repo_root>` itself, unchanged, when `work-on`'s no-config single-app fast path resolved the implicit app (see `work-on`'s Task 1). `apps/<name>` is one possible shape `<dir>` takes in a monorepo, never a literal path segment to hardcode — confirmed live: for a single-app repo (the primary use case per the README, not an edge case), `<app_dir>` is the repo root itself, and `cd`-ing into a literal `<repo_root>/apps/<app>` fails outright since that directory never exists. Resolve `<app_dir>` once per dispatch and use it everywhere below — never reconstruct an `apps/<app>` path by convention.

## Resolving the home directory — do not use shell `~` expansion

`~` expansion is shell-dependent and unreliable across platforms this tool's users are on (Windows shells don't expand it consistently). Resolve the base directory with:

```bash
python3 -c "from pathlib import Path; print(Path.home() / '.straw-boss')"
```

`pathlib.Path.home()` is documented cross-platform (`USERPROFILE` on Windows, `HOME` on POSIX). Use the resulting absolute path directly in every command below — never write a literal `~/.straw-boss/...` into a command.

## Capability record

`<home>/.straw-boss/capability.json`, written by `init`:

```json
{"mode": "herdr-enabled"}
```

or

```json
{"mode": "claude-p-only"}
```

## Instruction file — write it with `dispatch-task.py`, not by hand

One file per dispatch: `<home>/.straw-boss/dispatch/<app>--<short-slug>.json`. Plain JSON — this is machine-managed operational state, not a document.

```json
{
  "app": "api",
  "task": "Full task description as given to the agent — this is what gets submitted as the prompt in Task 4",
  "mode": "herdr-pane",
  "batch": null,
  "session_id": "<uuid>",
  "herdr_pane_id": null,
  "herdr_tab_id": null,
  "status": "pending",
  "created_at": "2026-08-16T10:00:00+08:00",
  "repo_root": "/absolute/path/to/your/repo"
}
```

Write this file — and generate the `session_id` — with the script, not a hand-rolled `Write` call:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/dispatch-task.py" write \
  --app <app> --slug <short-slug> --task "<task text>" --mode claude-p|herdr-pane \
  --repo-root <repo_root> [--batch <label>] [--plan <plan-slug> --task-id <task_id>]
```

Prints `{"session_id": "...", "instruction_path": "..."}` — use that `session_id` for the actual dispatch command below, don't generate a second one. For a plan task (`--plan`/`--task-id` given), this also marks `plan.json`'s matching task `dispatched` and refuses (before writing anything) if that task isn't still `planned` — a double-dispatch never leaves a stray pending file behind. It refuses outright if an instruction already exists at that `--app`/`--slug` pair, too.

`repo_root` is the absolute path of the project checkout this dispatch targets — required because instruction storage is no longer inside any particular checkout, so `app` alone (e.g. an app name) is ambiguous without it. `batch`, `herdr_pane_id`, `herdr_tab_id` are `null` until they apply. `status` moves `pending` → `in-progress` → `wrapped-up`.

Archived (wrapped-up) instructions move to `<home>/.straw-boss/dispatch/archive/<app>--<short-slug>.json`, same shape — see "Closing a herdr-pane instruction" below for how that move happens.

## Detecting the boss's own permission mode

SKILL.md's Task 4 requires mirroring this onto every agent. `$CLAUDE_PID` is already exported into the boss's own environment:

```bash
ORCH_ARGS=$(ps -p "$CLAUDE_PID" -ww -o args= 2>/dev/null)
case "$ORCH_ARGS" in
  *--dangerously-skip-permissions*|*--allow-dangerously-skip-permissions*)
    PERM_FLAGS="--dangerously-skip-permissions" ;;
  *"--permission-mode "*)
    PERM_MODE=$(echo "$ORCH_ARGS" | grep -oE -- '--permission-mode [a-zA-Z]+' | awk '{print $2}')
    PERM_FLAGS="--permission-mode=$PERM_MODE" ;;
  *)
    PERM_FLAGS="" ;;
esac
```

**Always produce a single token, never a bare `--permission-mode value` pair.** This environment's `Bash`/`Monitor` tools run under zsh, which does not word-split an unquoted variable the way bash does — `$PERM_FLAGS` expanding to two space-separated words would arrive at `claude`/`herdr` as one literal argument, not two, and fail to parse. `--permission-mode=<value>` (confirmed live to work identically to the two-word form) sidesteps this entirely by staying one token regardless of shell. Confirmed live: this detection correctly caught a real case a boss would otherwise have no reason to suspect — this session was itself running with `--dangerously-skip-permissions`. Only catches an *explicit* CLI flag; when `$PERM_FLAGS` comes back empty, the agent gets the CLI's own default (`auto`) and that's correct — there was nothing explicit to mirror. Append `$PERM_FLAGS` to the agent's launch command in both dispatch modes below, exactly where `--session-id`/`--name` already go.

## `claude-p` dispatch

```bash
cd "<app_dir>" && claude -p --session-id "<uuid from dispatch-task.py write>" $PERM_FLAGS "<task text>"
```

- Foreground (blocking): run as above and wait for exit — appropriate when the caller needs the result immediately.
- Background: use the Bash tool's `run_in_background`, then check back via the harness's own background-task notification — no separate tracking daemon needed.
- No trust-prompt handling needed: confirmed via `claude --help` that `-p`/print mode skips the workspace trust dialog automatically (non-interactive mode) — independent of whatever `$PERM_FLAGS` mirrors in.
- `claude -p --output-format json` gives a single structured result if the caller needs to parse the outcome programmatically; plain text output is fine for a report-back-to-user case.
- Once launched, confirm it per "Instruction file" above (`dispatch-task.py confirm --app <app> --slug <short-slug>`, no `--pane-id`/`--tab-id` needed for this mode) — the instruction should not sit `pending` after the process is actually running.
- If the boss itself is running inside a herdr pane, launching `claude -p` from it (even via `Bash`) overwrites that pane's own `agent_session` in `herdr pane list`/`agent list` to the subprocess's session id — cosmetic only, confirmed live, nothing documented here reads it, but don't use it to check "is this still my own pane."
- **Detecting the "ready to push/merge" checkpoint has no separate signal for a standalone `claude-p` dispatch — the process exiting *is* the signal.** On the full flow, the dispatch instruction tells the agent to stop and report readiness rather than execute a push/merge (see `shipping-task`'s Task 4) — commit itself needs no authorization and never stops the agent. `claude -p` processes exactly one turn then exits — so a foreground run returning, or a background run's harness-notification firing, means the agent either finished the whole task or (full flow only) hit that stop-and-report point; read its final output (already on stdout for a foreground run) to tell which. On the light flow there's no stop-and-report point at all — a `claude -p` process exiting always means the task actually finished (committed and done), never a checkpoint. There is no plan-style status file for a non-plan dispatch to poll instead — don't go looking for one.

## `herdr-pane` dispatch

0. **Ensure the boss itself is addressable — once per boss session, before the first `herdr-pane` dispatch, never skipped as "probably still fine from last time."** `/rename` does not persist across a session restart (see `cross-session-coordination.md` "Making the boss addressable"), so a freshly restarted boss is not addressable even if a prior session already did this. Check first rather than re-running blindly: `ListAgents` excludes the caller's own session, so there is no direct self-lookup — instead, treat "have I renamed myself this session" as a fact to track once and remember, not something to re-derive by calling any inspection command. If unrenamed, run the self-rename now, before writing any dispatch instruction that might need this channel.

1. **Resolve the tab.** Default to accumulating dispatched panes into the caller's own currently active tab (`$HERDR_TAB_ID`) rather than always opening a new one — this matches herdr's own guidance to default to a sibling pane in the current tab, and the 2x2-then-new-tab layout this was designed around.
   - If the instruction has a `batch` and another in-progress instruction with the same batch recorded a `herdr_tab_id`, check that tab still exists and has fewer than 4 panes (`herdr tab get <tab_id>` / `herdr pane list --workspace <id>` filtered to that tab) — prefer reusing it over the caller's own tab, so a multi-app batch's panes stay together.
   - Otherwise, check the caller's own current tab (`herdr pane list --workspace "$HERDR_WORKSPACE_ID"` filtered to `$HERDR_TAB_ID`): if it has fewer than 4 panes, use it.
   - Only create a new tab when neither applies (the caller's tab is already at 4 panes, or this is the overflow case below):
     ```bash
     herdr tab create --workspace "$HERDR_WORKSPACE_ID" --label "<batch-or-task-label>" --no-focus
     ```
     Read the new tab id from `.result.tab.tab_id` and the seed pane from `.result.root_pane.pane_id`.
2. **Pick a split direction from the existing layout**, don't always split the same way:
   ```bash
   herdr pane layout --pane <some-pane-in-that-tab>
   ```
   Wide pane → `--direction right`; narrow/tall pane → `--direction down`. If the tab already has 4 panes (2x2), don't split again — create another tab instead, labeled with a `-2`/`-3` suffix on the same batch label.
3. **Split and set cwd to the app directory:**
   ```bash
   herdr pane split --pane <target_pane_id> --direction right --cwd "<app_dir>" --no-focus
   ```
   Read the new pane id from `.result.pane.pane_id`.
4. **Start the claude agent with the session_id `dispatch-task.py write` printed:**
   ```bash
   herdr agent start "<unique-name>" --kind claude --pane <new_pane_id> -- --session-id "<uuid from dispatch-task.py write>" --name "<unique-name>" $PERM_FLAGS
   ```
   `<unique-name>` must match `[a-z][a-z0-9_-]{0,31}` and be unique among live agents (check `herdr agent list` first if unsure) — use the *same* value for herdr's own agent handle (the first argument) and the trailing `claude --name` flag. The former is herdr's own control handle (`herdr agent get/prompt/read/send-keys`); the latter is what makes this session addressable via `SendMessage`/`ListAgents` (confirmed live: without it, the session gets an auto-derived `<cwd-basename>-<suffix>` name instead) — see `references/cross-session-coordination.md`. Passing both costs nothing even when this dispatch never ends up using cross-session messaging.
5. **Handle the first-run trust prompt.** Check status:
   ```bash
   herdr agent get "<unique-name>"
   ```
   If `agent_status` is `blocked` (confirmed behavior: happens the first time `claude` opens a directory it hasn't seen before), clear it:
   ```bash
   herdr agent send-keys "<unique-name>" enter
   ```
   Then confirm it actually cleared before proceeding — don't submit the task prompt while still `blocked`. Use `herdr agent wait "<unique-name>" --until idle,blocked --timeout 15000` rather than a fixed `sleep` + single re-check: it's a real blocking primitive (`herdr agent --help`), returns the moment the state actually changes, and `--until blocked` still catches the (rare) case where clearing one prompt reveals a second one stacked behind it.
6. **Submit the task:**
   ```bash
   herdr agent prompt "<unique-name>" "<task text>" --wait --timeout 120000
   ```
   Omit `--wait` when the caller doesn't need an immediate result (fire-and-forget into the pane; the user can check on it later) — in that case, skip step 6.5 too and let a later status check confirm delivery instead.

   **Steps 6.5 through 8 are not optional follow-up — they finish this same dispatch.** An instruction left `pending` after its agent has visibly started working means one of them was skipped; don't treat "the task was submitted" as done.
6.5. **Confirm the task actually landed — do not trust the CLI's success return alone.** Confirmed live during testing: a first-run interruption (e.g. a one-time onboarding flow, or any other transient hiccup) can consume the submitted text while `herdr agent prompt --wait` still reports success and `agent_status` settles to `idle`. **`terminal_title` cannot tell you this on its own** — step 4 always passes `--name`, and that alone renames the pane's terminal title away from its generic default the moment the agent starts, before any task is ever submitted (confirmed live: the title had already changed to the `--name` value while the pane was still sitting on the cleared trust prompt, with no task sent yet), so "no longer generic" proves the agent started, not that this task landed. Instead, `herdr agent read "<unique-name>" --lines 40` and confirm the transcript shows real assistant output that follows the submitted task text — not just the task text sitting unanswered, and not still the pre-task trust-prompt screen. If it doesn't, resubmit the prompt once (repeat step 6), then re-check. If still not confirmed after one retry, stop and tell the user rather than marking the instruction `in-progress`.
7. **Cross-check the session id.** `herdr agent get "<unique-name>"` now returns `.result.agent.agent_session.value` (confirmed field path, present once the claude integration hook — see `init` — has reported in). Compare it to the session_id passed in step 4; if they don't match, flag this to the user rather than silently trusting either value.
8. **Confirm the dispatch**, recording `herdr_pane_id`/`herdr_tab_id` and flipping the instruction to `in-progress`:
   ```bash
   uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/dispatch-task.py" confirm \
     --app <app> --slug <short-slug> --pane-id <new_pane_id> --tab-id <tab_id>
   ```
   Refuses if the instruction isn't still `pending` — don't call this before step 6.5 has actually confirmed delivery. Do this immediately after step 7, in the same span of actions as steps 4-6 — not as a separate later chore; confirmed live during testing this is exactly the step that gets forgotten when it's treated as an afterthought.

For `claude-p`, there's no pane/tab to record — call the same `confirm` without `--pane-id`/`--tab-id` once the process has actually been launched.

### Closing a herdr-pane instruction (wrap-up)

- If the instruction's tab is shared with other still-in-progress instructions from the same batch, close only its pane: `herdr pane close <pane_id>`.
- If it was the last active pane in its tab (check `herdr pane list` for that `tab_id` first), close the tab too: `herdr tab close <tab_id>`.
- Never close a pane/tab this skill didn't create, and never run `herdr server stop`.
- Once any pane/tab this skill owns is closed (or, for `claude-p`, immediately — there's nothing to close), archive the instruction and sync `plan.json` (if it's a plan task) with the script, not a hand-rolled `mv` + `Edit`:
  ```bash
  uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/wrap-up-task.py" \
    --app <app> --slug <short-slug> [--plan <plan-slug> --task-id <task_id>]
  ```
  For a plan task, this reads the task's own status file and refuses to archive unless it reports a terminal state (`done`/`failed`) — it will not wrap up a task that's `awaiting-authorization` or `awaiting-user-input`, matching `plan-mechanics.md`'s auto-detach rule. It never touches a pane, tab, or worktree itself — those stay the live tool calls above and in `plan-mechanics.md`'s "Worktree ownership."

## No `herdr group` primitive

`herdr group` is not a valid command (confirmed: `unknown command: group`), and no `pane`/`tab`/`workspace` subcommand takes a `--group` flag. Batch grouping is entirely the tab + `--label` mechanism above — don't implement or reference a `group` concept that doesn't exist in the installed CLI.
