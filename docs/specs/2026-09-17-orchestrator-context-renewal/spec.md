Status: approved
Approved at: 2026-09-17
Approved from: User replied "好" to the proposed spec after reviewing its five flagged choices (5% target, single-use record, loop guard, live-run cost, provider fallback).

# Context renewal for long-lived Straw Boss sessions

Decisions and evidence: [decision.md](decision.md).
Baseline: `~/.claude/state/weihung-user-claude/token-sinks/baseline-2026-09-03_2026-09-18.txt`.

## Covered sessions

A covered session is a main agent, a dispatched worker, or a standalone worker that `boss-say` runs without a main agent, on Claude Code, Codex, or Antigravity.

## Observable behavior

1. **Trigger.** When a turn of a covered session ends with its context above 200k tokens, the session renews before it handles its next user or agent message.
2. **Continuity record.** Before clearing, the session writes one record under `~/.straw-boss/` keyed by its Herdr pane. The record holds the role (main agent, dispatched worker, or standalone worker), the continuity payload (goal and scope, confirmed decisions and user terms, current state and evidence, next action, exclusions), and the dispatch instruction paths the session owns or serves. A dispatched worker also writes its progress checkpoint, so the stop guard lets the turn end.
3. **Notice.** The session prints one line naming the renewal and the record path, and asks no approval question.
4. **Clear.** In Herdr, the session's own pane receives the provider's clear command after the turn ends. Outside Herdr, the notice asks the user to run that command.
5. **Injection.** The session that the clear starts in that pane receives the record through its SessionStart hook, is primed for the recorded role, and continues the recorded next action without the user restating context. Only a main agent receives main-agent priming. The record is consumed once.
6. **Main agent continuity.** After renewal, the main agent's existing dispatches accept its commands, worker `done` and `failed` notifications reach it, and the orchestrator directory lists the renewed session with the same scope.
7. **Dispatched worker continuity.** After renewal, the worker's status reports, checkpoints, and stop guard accept the renewed session in the recorded worker pane, and its main agent sees no identity refusal.
8. **Standalone worker.** Renewal completes with no dispatch record and no main agent.
9. **User input.** A user message submitted while renewal runs reaches the renewed session.
10. **Backstop.** After the `weihung-user-claude` installer runs, Claude Code sessions auto-compact at 300k through the global `autoCompactWindow`, and Codex sessions compact at 300k through `model_auto_compact_token_limit`. Antigravity has no backstop and relies on renewal.
11. **Compaction priming.** After a backstop compaction, the SessionStart hook primes the session for its existing role, as it does today.

## Edge cases

- A turn that crosses 200k mid-turn finishes uninterrupted; the backstop bounds it.
- A renewed session whose first turn already starts above 200k reports that once instead of renewing again.
- A record whose pane no longer exists is never injected into another pane.
- A clear with no pending record behaves exactly as it does today.
- A coworker pane in the same tab renews under its own pane key.

## Compatibility constraints

- Identity validation still refuses any caller that is not the session running in the recorded pane; adoption extends only to that session.
- `handoff-orchestrator`, dispatch contracts, and status file formats keep their current interfaces.
- Sessions outside Straw Boss receive only the backstop; `/autocompact` still overrides the window per session.
- A provider that Design proves cannot measure context, clear its own pane, or run a SessionStart hook returns to this spec for a user decision before implementation.
- The Straw Boss plugin version is bumped and installed through `scripts/install.sh`; `weihung-user-claude` ships the backstop settings through its installer.

## Non-goals

- Shrinking tool output, the fixed prompt prefix, or model routing.
- An Antigravity backstop before agy exposes a compaction setting.
- Changing when or how `handoff-orchestrator` moves scope to a new tab.

## Applied standards

- `CONTEXT.md` vocabulary (main agent, dispatched agent, continuity payload, session identity) and role authority in `skills/i-am-orchestrator/SKILL.md`: new records and skills use these terms.
- `aaaav-do` durable workflow: Design settles provider mechanics and the Herdr self-clear prototype before production edits.
- `weihung-user-claude` engineering rules (minimum code, surgical changes) and `rules/python.md` for new scripts.

## Reality anchor

1. **Executable:** the Straw Boss unittest suite, extended for record writing and consumption, role-aware SessionStart priming, worker-side adoption, and per-provider threshold detection.
2. **Pseudo-human live run:** in Herdr, for each of Claude Code, Codex, and Antigravity, a main agent with one dispatched worker and one standalone worker are driven above 200k by reading large files. Observe the notice, the clear, the injected record, the continued next action, a worker `done` reaching the renewed main agent, and a user message typed during renewal being answered.
3. **Measurement:** `scripts/token-sinks.py` over the first 7 days after installation shows calls above 400k context carrying at most 5% of cost, against 49.2% in the baseline.
4. **Human:** after those 7 days, the user judges whether renewed sessions continued without the user restating context.

Checkpoint: anchors 1 and 2 pass before installation; anchors 3 and 4 close the change 7 days after installation.
