# Dispatch mechanics

Operational state lives under `Path.home() / ".straw-boss"`; target project
files are never modified to inject a dispatch workflow.

## Resolve mode and work route

- `capability.json` explicitly says `claude-p-only`: use headless mode.
- Otherwise use `herdr-pane` when `HERDR_ENV=1`; use headless only when no live
  herdr session exists.
- Resolve the worker setup independently: explicit per-dispatch override, then
  a matching work route in root `CLAUDE.md`, then the app's
  `apps.json.agentKind`, then Claude with provider defaults. A work route can
  select agent kind, provider profile, model, effort, and a Claude Code native
  advisor. Codex has no native advisor; refuse that combination.

Resolve `<app_dir>` from the app configuration; never assume `apps/<app>`.

## Write the instruction and contract

Before launching anything, call:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/dispatch-task.py" write \
  --app <app> --slug <slug> --task "<task>" \
  --mode claude-p|herdr-pane --repo-root <repo_root> \
  [--batch <batch>] [--plan <plan> --task-id <task>] [--role <workroom>] \
  --agent-kind claude|codex --main-agent-kind claude|codex \
  [--agent-profile <profile>] [--agent-model <model>] \
  [--agent-effort <effort>] [--advisor-model <claude-model>] \
  [--main-agent-pane-id <pane>] \
  [--main-agent-session-id <session> | --main-agent-terminal-id <terminal>]
```

Pass `--role` when the brief already names a short workroom the task belongs to
(e.g. `database`, `frontend`, `api`) — distinct from `--app` when several tasks
share one app but work different concerns. The launcher's derived agent name
prefers it over `--app`; omit it only when no such label is actually known.

For `herdr-pane`, obtain the main-agent pane and provider fingerprint from the
current live Herdr record: Claude uses `agent_session.value`; Codex uses
`terminal_id`. The command creates:

- `<app>--<slug>.json`: pending instruction and receiver fingerprints;
- `<app>--<slug>.contract.md`: mandatory workflow text;
- a SHA-256 contract digest recorded in the instruction.

The contract contains the exact instruction-keyed progress, question, and
status commands. The task prompt carries work semantics, not a hand-copied
workflow.

## Permission mapping

Mirror the main agent's restriction tier; the dispatched agent must never be
more permissive.

| Tier | Claude | Codex interactive | Codex headless |
|---|---|---|---|
| unrestricted | `--dangerously-skip-permissions` | `--dangerously-bypass-approvals-and-sandbox` | same |
| guarded-write | default/`auto`/`acceptEdits`/`dontAsk` | `--sandbox workspace-write --ask-for-approval on-request` | `--sandbox workspace-write` |
| read-only | `plan`/`manual` | `--sandbox read-only` | `--sandbox read-only` |

Detect explicit Claude mode from `ps -p "$CLAUDE_PID" -ww -o args=`. Preserve
each flag as one argument; do not depend on shell word splitting.

## Interactive herdr launch

Omit `--name` and the launcher derives a unique operator-visible handle itself
from the instruction's `role` when `write` recorded one, else its `app`
(`<workroom>-worker`, or `<workroom>-coworker` for a dispatch with a
`parent_instruction_path`) — so two tasks sharing one `app` but different
`--role`s (e.g. `database`, `frontend`) still read as distinct at a glance, not
as `<app>-worker`/`<app>-worker-2`. It checks `herdr agent list` first and, if
`herdr agent start` still rejects the chosen name as `agent_name_taken` (a
sibling task in the same wave won the race), retries with the next
collision-suffixed candidate, up to a bounded number of attempts. An explicit
`--name` overrides derivation and is used as given with no retry — a
collision on it is the caller's to fix; validate one first with
`check-agent-name.py` if hand-picking. The launcher resolves the instruction's
recorded main pane and splits the worker into that same tab with `repo_root`
as cwd. Internally it runs
`herdr pane split <main-pane> --direction right --cwd <repo_root> --no-focus`.
Run only:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/launch-dispatched-agent.py" \
  --instruction-path <instruction path> \
  [--name <agent name>] \
  [--agent-arg <one provider argument>]...
```

The launcher derives provider arguments from the recorded worker setup, then:

1. verifies the instruction is pending and the contract digest matches;
2. resolves the worker's name as above;
3. injects Claude with `--append-system-prompt-file`, or Codex with
   `developer_instructions`;
4. resolves the main pane and splits a worker pane in the same tab;
5. starts the provider through herdr and handles an initial trust prompt;
6. submits the recorded task; when the pane was idle, already done, or
   blocked (not yet already working) just before sending, also requires
   herdr's own `--wait`/`agent_prompt_stalled` lifecycle gate to confirm a
   turn actually started, not merely that the text reached the composer;
   either way polls until its whitespace-normalized text appears in the
   provider-appropriate transcript view; retries once only after a
   herdr-confirmed stall or a complete transcript miss; two failures of
   either kind fail launch and remove the worker pane;
7. records the live provider fingerprint: Claude waits for
   `agent_session.value` and cross-checks its preassigned id; Codex records
   `terminal_id` without waiting for a session field;
8. writes `<app>--<slug>.launch.json` with the worker pane and shared tab;
9. on a top-level dispatch (never a coworker's), best-effort-names the
   coordinator's own still-unnamed pane `<app>-coordinator` — an already-named
   coordinator pane is left alone, and a failure here never fails the launch
   that already succeeded.

Provider profile/model/effort are instruction-owned. Claude receives
`--agent`/`--model`/`--effort`; Codex receives
`--profile`/`--model`/`model_reasoning_effort`. Claude additionally receives
`--advisor <advisor_model>` when recorded. `--agent-arg` carries permission or
other provider options; duplicating an instruction-owned option is refused.

Confirm only after the launcher returns:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/dispatch-task.py" confirm \
  --app <app> --slug <slug>
```

Confirmation consumes the receipt and refuses any instruction, contract,
provider, pane, or provider-fingerprint mismatch. It records the receipt values
and moves the instruction to `in-progress`.

Herdr accepting `agent prompt` is not delivery proof -- text can land in an
agent's composer without ever starting a turn. The launcher writes the
receipt only after herdr's own lifecycle gate (where the pane's pre-send
state makes it available) confirms a turn started and the transcript shows
the delivered text, so `confirm` cannot advance a task whose startup flow
only wrote its prompt into the composer or swallowed both task submissions.

## Headless launch

Headless mode has no live receiver. Inject the generated contract in the same
invocation that starts the process:

```bash
claude -p --session-id <instruction session_id> \
  --append-system-prompt-file <contract path> <permission flags> \
  [--agent <agent_profile>] [--model <agent_model>] \
  [--effort <agent_effort>] [--advisor <advisor_model>] "<task>"
```

or:

```bash
codex exec --json <permission flags> \
  -c developer_instructions="$(<contract path>)" \
  [--profile <agent_profile>] [-m <agent_model>] \
  [-c model_reasoning_effort=<agent_effort>] "<task>"
```

Codex has no native advisor. `dispatch-task.py write` refuses its
`--advisor-model` before creating an instruction; never emulate one with a
coworker or subagent.

The process must write status through `report-task-status.py
--instruction-path` before exit. With no live main-agent endpoint, that
persisted status plus the process's own exit is what the main agent reads. A Codex
continuation uses its separately recorded provider thread id with
`codex exec resume` and includes the same contract content again. The interactive
Herdr `terminal_id` is only a live routing fingerprint and never substitutes for
that thread id.

## Reporting and communication

- Progress: `report-progress.py --instruction-path ... --note ...`
- Checkpoint/outcome: `report-task-status.py --instruction-path ... --status ... [--ref ...]`
- Generic question/FYI: `send-dispatch-message.py --instruction-path ... [--ref ...]`
- Checkpoint reply: `reply-to-worker.py --worker-instruction-path ... [--ref ...]`

Only these public scripts send cross-session messages. They resolve endpoints
from the instruction and validate provider-specific live fingerprints. The Plan
watcher observes durable content revisions and remains scheduling authority.

## Closing an instruction

Close only the worker pane created for the dispatch; the shared tab belongs to
the coordinator. Then call `wrap-up-task.py`; it
archives the instruction and its contract, receipt, status, progress, and
delivery artifacts, and synchronizes terminal Plan status. Never archive a
non-terminal checkpoint or a task with a same-task continuation pending.

If the worker pane already closed before it wrote its own terminal status,
`report-task-status.py`'s sender validation makes it impossible for the
coordinator to write `done`/`failed` on its behalf while posing as the
worker — by design, so a live worker is never overridden.
`recover-task-status.py --instruction-path ... --status done|failed --note
...` is the one explicit exception: it confirms the caller is the genuine
live main agent, then confirms the worker pane is actually unreachable (a
herdr probe, not an assumption), then writes the status file itself with a
`recovered_by_main_agent` marker. It refuses if the worker pane still
answers, or if a terminal status is already on file. This is recovery for a
pane that already closed, not a substitute for the normal reply-then-
self-report order — see `SKILL.md`'s Wrap-up branch Step 4.

## Worker-owned coworker

An interactive dispatched worker that needs a human-facing second opinion uses
`bringing-coworker`. Its facade derives identity and placement from the parent
instruction; the top-level dispatch flow does not recreate those mechanics.
