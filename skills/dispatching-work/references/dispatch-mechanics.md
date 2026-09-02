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
  [--retry-failed-plan-task] \
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

`--retry-failed-plan-task` applies only after a headless Claude plan attempt has
reported terminal `failed`, been wrapped, and received its user-owned answer.
Preserve its team-mode worktree, reuse the same `repo_root`, use a fresh dispatch
slug, and carry the answer in the new brief. The write
removes the old failed status and returns that same plan task to `dispatched`.

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
5. starts the provider through herdr, then applies the final collision-resolved
   agent name to the worker pane before task delivery. Pane naming retries once;
   a second failure returns a warning and keeps the dispatch path active;
6. settles on herdr's own state wait
   before reading the agent — a single read straight after `agent start`
   catches a Claude worker still reporting `idle`/`interactive_ready` while a
   first-run gate is mid-render;
7. handles a startup gate by provider. Codex's own startup trust prompt is
   confirmed with `enter`. **A blocked Claude worker is never answered
   blindly**: Claude Code's startup gates — folder trust first among them —
   render as a select list whose highlighted option is `No, exit`, so `enter`,
   or the task itself which ends in one, exits the worker herdr had just
   reported healthy. The launcher reports the gate with what the pane is
   showing and leaves the pane standing for whoever answers it;
8. submits the recorded task; when the pane was idle, already done, or
   blocked (not yet already working) just before sending, also requires
   herdr's own `--wait`/`agent_prompt_stalled` lifecycle gate to confirm a
   turn actually started, not merely that the text reached the composer;
   either way polls until its whitespace-normalized text appears in the
   provider-appropriate transcript view; retries a herdr-confirmed stall or a
   complete transcript miss on a backoff, and a booted worker whose prompt
   still never lands keeps its pane;
9. records the live provider fingerprint: Claude waits for
   `agent_session.value` and cross-checks its preassigned id; Codex records
   `terminal_id` without waiting for a session field;
10. writes `<app>--<slug>.launch.json` with the worker pane and shared tab, and
   clears any `<app>--<slug>.launch-failure.json` an earlier run left;
11. on a top-level dispatch (never a coworker's), best-effort-names the
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

### When a launch fails

The launcher retries the whole sequence itself, bounded and backed off, so a
transient trip never becomes four hand-run relaunches. It retries only what a
second attempt can clear — herdr reporting the agent or pane gone
(`agent_not_running`, `agent_not_found`, `pane_not_found`, `agent_pane_busy`).
A refused start, a mismatched identity, a pane in the wrong tab, or a startup
gate is a standing condition of this cwd or configuration: those are reported
at once, because a fourth identical attempt only burns another pane and delays
the answer.

Every failure carries the worker pane's own visible output. herdr's error code
says the agent is gone and never says why; the agent's last words — a trust
gate, a refused session id, a crash — exist only on that pane, and the cleanup
closes it. A failing attempt reads the pane first and reports the excerpt.

A pane is closed on failure unless its agent is still alive and someone can act
on it there: a startup gate awaiting an answer, a booted worker whose opening
prompt never landed, or one whose task was already confirmed delivered and only
this launcher's own identity bookkeeping then failed. Those keep their pane and
the error says so — the worker in the last case is doing the task while its
instruction stays `pending`, which is the `launched-unconfirmed` row the roll
call reports.

A Claude startup gate is only described as a trust dialog when the pane
actually shows its preselected option; a worker that is merely `blocked` before
its first turn is reported as that, with the pane's contents and no prescribed
keystrokes for a dialog the launcher has not recognised.

Every failed launch writes `<app>--<slug>.launch-failure.json` beside the
instruction: one entry per attempt with its pane, session id, classification,
error, and pane excerpt. Without it a failed launch leaves the instruction
`pending` with no receipt and no pane id — indistinguishable from a dispatch
nobody ever started. `wrap-up-task.py` archives this file with the instruction,
and `roll-call.py` reads it to say why a `never-launched` row is stuck.

`claude --session-id` refuses an id it has already seen and exits at once, so
each retry — and any rerun whose recorded attempt trail shows the id already
spent — mints a fresh session id into the still-`pending` instruction before
starting. Reusing a spent id guarantees a startup death, so relaunching a
dispatch whose first attempt booted an agent would otherwise be impossible.

## Roll call

`roll-call.py` is the read-only reconciliation of live herdr state against
`~/.straw-boss/dispatch/`. It starts nothing, closes nothing, writes nothing.

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/roll-call.py" [--mine] [--json]
```

**Liveness is decided by `agent_session.value` (Claude) or `terminal_id`
(Codex) together with `agent_status` — never by a pane's terminal title.** A
title only reflects whatever the foreground program last set, so an idle
worker's pane reads back as a plain shell prompt while the agent is perfectly
alive. Reading that as death is what let one coordinator declare another's live
worker an orphan and dispatch the same task a second time. The same rule makes
the recorded pane id secondary: a closed pane's id can be reissued to somebody
else's agent later, so matching on it would report a stranger as this
dispatch's worker.

Per-dispatch verdicts: `running`, `checkpoint` (waiting at an `awaiting-*`
status), `awaiting-collection` (its own status record is terminal),
`orphaned` (no live agent carries this worker's fingerprint), `never-launched`
(still `pending`, with the launch-failure reason when one was recorded),
`launched-unconfirmed` (an agent carries the dispatch's fingerprint but
`dispatch-task.py confirm` never recorded it — a half-landed launch, never a
free slot to dispatch into again), and `awaiting-startup-gate` (a failed launch
deliberately kept its pane and it is still open, waiting on a human).

The worker fingerprint is read from the instruction **and its launch receipt**,
because the instruction carries no usable one until `confirm` runs — for Codex
none at all (`herdr_terminal_id` is written only at confirm), for Claude only
the preassigned id. A pane a launch kept on purpose is matched through the
launch-failure record instead: that worker has not taken its first turn, so
herdr exposes no `agent_session` for it yet, and the record is the only thing
tying the pane back to its dispatch. Both windows exist precisely where a
worker looks absent while it is not.
Every row names the coordinator pane and session that dispatched it, and says
when that coordinator's own session is no longer live.

A dispatch nothing is matched to also reports any live agent sitting in its
`repo_root`, and those agents carry the reverse pointer in the section below.
That is a caution, never an attribution, and it never changes a verdict: a
coworker shares its parent's worktree, and a worker started by hand outside
`launch-dispatched-agent.py` carries a session id no instruction ever recorded.
It is still the one fact that stops "nothing carries this fingerprint" being
read as "nothing is running for this dispatch" — which is the duplicate
dispatch again.

A second section lists live agents with no instruction of their own, split into
`coordinator` (its session appears as some instruction's
`main_agent_session_id`) and `unattributed`. **`unattributed` means "not
attributable from this data", never "ownerless".** A coordinator pane has no
instruction by design, and a freshly split worker pane has none until its
dispatch reaches `dispatch-task.py write` — closing one of those on the "no
instruction" reading is the second half of the same incident.

`--mine` narrows the dispatch list to the ones this pane dispatched, for a
machine running several coordinators at once, matching on this pane's own
session value or terminal id (a Codex coordinator has only the latter). It
refuses when neither resolves rather than falling back to "everything is
mine" — that fallback would answer the one question `--mine` exists to answer,
wrongly and silently. It never narrows attribution either: every instruction is
still read, or filtering would manufacture exactly the ownerless-looking agent
this script exists to prevent anyone acting on.

Herdr accepting `agent prompt` is not delivery proof -- text can land in an
agent's composer without ever starting a turn. The launcher writes the
receipt only after herdr's own lifecycle gate (where the pane's pre-send
state makes it available) confirms a turn started and the transcript shows
the delivered text, so `confirm` cannot advance a task whose startup flow
only wrote its prompt into the composer or swallowed both task submissions.

## Headless launch

Headless mode has no live receiver. Start it through the provider-aware runner,
which injects the generated contract in the same invocation:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/run-headless-dispatched-agent.py" \
  start --instruction-path <path> [--agent-arg=<permission-flag>]...
```

Codex has no native advisor. `dispatch-task.py write` refuses its
`--advisor-model` before creating an instruction; never emulate one with a
coworker or subagent.

The process must write status through `report-task-status.py
--instruction-path` before exit. With no live main-agent endpoint, that
persisted status plus the process's own exit is what the main agent reads. The
runner holds one instruction-level claim across provider start or resume, so a
duplicate command cannot launch or continue the same task concurrently. It
captures Codex's `thread.started` event before accepting a checkpoint.
Continue it with:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/run-headless-dispatched-agent.py" \
  resume --instruction-path <path> --answer "<answer>"
```

That command uses the recorded provider thread id with `codex exec resume`,
reinjects the contract, and requires a new status revision. The interactive
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
