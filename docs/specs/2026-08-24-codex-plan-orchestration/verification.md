# Codex Plan orchestration verification

> Historical evidence for the earlier transport. Current behavior is verified
> under `docs/specs/2026-08-25-dispatched-agent-lifecycle-transport/`.

## Automated evidence

- `python3 -m unittest discover -s tests -v`: 15 passed. Covers both endpoint
  providers, required main-agent metadata, cross-provider peer rejection,
  Claude-to-Claude fallback, write-before-herdr ordering, preserved status on
  herdr failure, cancellation without self-notification, dependency release,
  checkpoint replies, watcher recovery, and herdr-first Claude/Codex peer
  questions.
- `python3 -m compileall -q scripts tests`: passed.
- `openspec validate --all --strict`: 7 items passed, 0 failed.
- `git diff --check`: passed.

## Agent-operated interface observations

- A fake `herdr` executable asserted the Plan status file already existed when
  `herdr agent prompt` ran, proving persistence precedes live notification.
- Claude worker to Codex main-agent dispatch wrote no SendMessage peer,
  `get-main-agent.py` selected `herdr`, and the status CLI prompted the recorded
  pane.
- A failing herdr executable made the status CLI exit non-zero while the
  terminal status remained readable by the watcher.
- A headless Claude-to-Claude instruction selected `send_message`; every
  cross-provider attempt to record that peer failed before dispatch state was
  written.
- The `asking-peer-agents` contract addresses both Claude and Codex peers by
  recorded herdr pane and limits `SendMessage` to a Claude-to-Claude fallback.

## Contract review

- Current architecture, skills, canonical OpenSpec specs, and active deltas all
  describe herdr as primary and `SendMessage` as Claude-to-Claude fallback only.
- Plan scheduling depends on persisted status plus `watch-plan-status.py`; live
  herdr notification is ordered behind the write and does not replace recovery.
- Archived OpenSpec changes remain historical and were not rewritten.

## Delivery boundary

The change is implemented and verified locally. No commit, push, release, or
deployment was performed.
