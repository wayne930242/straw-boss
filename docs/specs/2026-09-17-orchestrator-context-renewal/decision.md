# Orchestrator context renewal

Outcome: a long-lived Straw Boss main agent keeps its per-call context small by continuing from persisted coordination state instead of carrying its whole conversation toward the 1M window.
Actors: the user, the main agent, dispatched agents whose routes are bound to the main agent's session and pane.

## Evidence

Baseline from `weihung-user-claude/scripts/token-sinks.py --since 2026-09-03 --until 2026-09-18`, saved at `~/.claude/state/weihung-user-claude/token-sinks/baseline-2026-09-03_2026-09-18.txt`:

- Cached reads are 78.9% of cost and output is 7.2%; every call re-reads its whole context.
- Calls made with more than 400k context carry 49.2% of cost; sessions regularly reach about 965k with 27 compactions across 692 sessions.
- The `moldplan-center` root, where main agents run, carries 23.8% of cost; worktree and app-rooted worker sessions carry most of the rest and also reach about 965k.
- In root main-agent sessions over the same period, 16.8% of calls read files (`cat`, `sed`, `grep`, `Read`) at a mean context of 280k, and 9 of 19,466 calls used a native subagent.

## Existing mechanisms

- `scripts/adopt-dispatch.py` lets a new session running in the recorded main pane adopt the dispatches that pane made.
- `scripts/orchestrator-priming.py` re-primes a main agent on SessionStart sources `startup`, `clear`, and `compact`, and skips dispatched workers by session id.
- `handoff-orchestrator` defines the continuity payload (goal and scope, confirmed decisions and user terms, current state and evidence, next action, exclusions) and moves it to a new user-approved tab; `~/.straw-boss/handoffs/` holds no records.
- `register-orchestrator.py` keys the orchestrator directory on the provider session fingerprint.

## Decisions

| Question | Answer | Basis | Status |
|---|---|---|---|
| Is per-call context size the cost driver to reduce? | Yes. | Baseline cost composition and context-size split above. | grounded |
| Can a fresh session in the same pane keep coordinating existing dispatches? | Yes, through `adopt-dispatch.py`. | `scripts/adopt-dispatch.py` docstring. | grounded |
| Does a fresh or cleared main-agent session get its operating stance back? | Yes, through SessionStart priming on `clear` and `compact`. | `scripts/orchestrator-priming.py`. | grounded |
| Which sessions does renewal cover: root main agents only, or dispatched workers too? | Main agents, dispatched workers, and standalone workers that `boss-say` runs without a main agent. | User answers on 2026-09-17; root carries 23.8% of cost and workers carry most of the rest. | confirmed |
| Where does a renewed session get its continuity back? | The SessionStart hook injects the persisted continuity payload for its pane after `clear`. | User direction on 2026-09-17; `orchestrator-priming.py` already runs on `clear`. | confirmed |
| How does the SessionStart hook tell a renewed worker from a main agent? | From the role recorded in the continuity payload, because a cleared worker has a new session id that no dispatch instruction records. | `orchestrator-priming.py` skips workers by matching the session id against dispatch instructions. | grounded |
| How does a renewed dispatched worker keep reporting status? | Its new session in the recorded worker pane adopts the dispatch, mirroring `adopt-dispatch.py` on the main-agent side. | Status and stop-guard commands validate the recorded worker session. | grounded |
| Which mechanism keeps context small: same-pane renewal from a persisted continuity payload, a smaller context window that makes compaction fire early, or both? | Both: same-pane renewal from a persisted continuity payload is the primary path, and a smaller context window is the backstop. | User answer on 2026-09-17. | confirmed |
| Can Claude Code compact earlier than the 1M window? | Yes: `claude --autocompact <100k–1M>`, the `autoCompactWindow` user setting, or `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, which takes precedence; the default is about 967k, including on native-1M models such as Sonnet 5 and Fable 5.1. | code.claude.com/docs/en/model-config; `claude --help` on 2.1.274. | grounded |
| What signal starts renewal, and at what context size? | A hook cues renewal at a turn boundary once context exceeds 200k; the backstop compaction window is 300k. | User answer on 2026-09-17; cost split: ≤200k 19.8%, 200–400k 31.0%, >400k 49.2%. | confirmed |
| Where does the backstop compaction window apply: a global user setting or Straw Boss launches only? | Global user settings for every provider that exposes one: Claude Code `autoCompactWindow`, Codex `model_auto_compact_token_limit`. | User answer on 2026-09-17; main agents and standalone workers start from a user-launched CLI. | confirmed |
| Do Codex and Antigravity sessions follow the same renewal model? | Yes; provider-specific context measurement, clear command, and SessionStart hook mechanics are settled in Design. | User direction on 2026-09-17. | confirmed |
| Can Antigravity take a backstop compaction window? | Not through a public setting: agy 1.2.5 has an internal `HarnessConfig.compaction_threshold` but no CLI flag or `settings.json` key, so agy sessions rely on renewal alone until agy exposes one. | `agy --help`, `~/.gemini/antigravity-cli/settings.json` keys, and binary strings on 2026-09-17. | grounded |
| Can Codex take a backstop compaction window? | Yes, `model_auto_compact_token_limit` in Codex `config.toml` or as a `-c` override. | codex-cli 0.154.0 binary strings on 2026-09-17. | grounded |
| How does the `weihung-user-claude` installer set the Codex backstop while `config.toml` stays user-owned? | It manages only that top-level key from `config/codex-managed.toml`, keeps every other line, and uninstall removes the key while it holds the installed value. | User answer on 2026-09-17. | confirmed |
| Who performs the clear? | The session clears itself after persisting continuity; a Design prototype proves Herdr delivers `/clear` into the session's own pane after its turn ends. A session outside Herdr tells the user to run `/clear`. | User direction on 2026-09-17; delivery into the session's own pane is unverified. | confirmed |
| Does same-pane renewal need user approval each time? | No; the session announces renewal in one line and renews only between turns. | User answer on 2026-09-17. | confirmed |
| How is success measured? | Run `token-sinks.py` with `--root` set to the main agent's transcript directory over an equal-length window after rollout, and compare the cost share of calls above 400k context with the baseline. | Baseline method above. | grounded |

Core rules readiness: Straw Boss authority lives in `skills/i-am-orchestrator/SKILL.md`, dispatch identity rules in `skills/dispatching-work/references/`, and the durable workflow in `aaaav-do`; implementation waits for the open rows above.
