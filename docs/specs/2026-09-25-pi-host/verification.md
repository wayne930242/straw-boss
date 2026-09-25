# Pi host support — verification

Spec: [spec.md](spec.md). Evidence was collected on 2026-09-25/26 on the uncommitted working trees of `straw-boss`, `weihung-user-claude`, and `moldplan-center`.

## Requirements

| Requirement | Evidence | Result |
|---|---|---|
| 1. The Pi manifest loads exactly the six skills and two extensions | `tests/test_pi_package.py` resolves the checkout through Pi's own `DefaultPackageManager` and gets exactly the six `pi/skills/` directories and two extensions. Pi's `DefaultResourceLoader`, run in `moldplan-center` with the real agent directory, lists all six from `straw-boss/pi/skills/` and both extensions with 0 extension errors. | pass |
| 2. The moved extension and helper keep their behavior | `tests/test_pi_dispatch.py` (the moved CLI, handoff-commit, and receiver-start tests) and the six moved Node suites under `tests/pi/` pass. `pi/extensions/dispatch-recovery.ts` changed only its helper path. The ledger, handoff, and delivery directories still derive from `PI_CODING_AGENT_DIR`. | pass |
| 3. Other hosts unchanged | `git diff HEAD -- skills` is empty, and `tests/test_pi_skills.py` asserts it. The Claude/Codex manifests changed only their version. `transport.py` gained an env override whose default stays 2.0 s, asserted by `tests/test_prompt_delivery_evidence.py`. Full suite: 645 passed. | pass |
| Pi branch runs no file under `scripts/` | `tests/test_pi_skills.py` rejects `scripts/`, `CLAUDE_PLUGIN_ROOT`, plan files, `awaiting-*` states, and other-host skills anywhere in `pi/skills/`. | pass |
| 4. Route | Live smoke test `sb-pi-smoke2`: a fresh Pi main agent in `moldplan-center` loaded `boss-say`, named the single-loop graph and the adversarial-review anchor, and classified the request as read-only with no lifecycle mode. | pass |
| 5. Resolve | The same run resolved `mqtt-monitor` from `.claude/straw-boss/apps.json` after finding `.straw-boss/apps.json` absent. | pass |
| 6. Worker setup | The same run passed the `recon` tier's full model list and thinking to the worker, and the `review` tier's to the checkpoint reviewer. | pass |
| 7. Checkout: solo and read-only | The read-only worker launched with the app directory as `cwd` and no worktree. | pass |
| 7. Checkout: team-mode worktree and `localFiles` | Not exercised live; the steps are plain git and `cp -R` written in `pi/skills/dispatching-work`. | unknown |
| 8. Brief and worker contract | The worker returned an explanatory result with file-line evidence, as the read-only branch of the contract asks. | pass |
| 9. Schedule | Both dispatches were tracked as todo items. Multi-task dependency scheduling was not exercised live. | unknown |
| 10. Events: result, adversarial-review checkpoint | The result arrived automatically. The main agent launched `mqtt-entry-review`, which returned PASS WITH NITS, and corrected the cited line numbers in its report. | pass |
| 10. Events: `caller_ping` → `ask_user` → `subagent_resume`, stall notice | Not exercised live. | unknown |
| 11. Mutation checkpoints | Written in `pi/skills/shipping-task`; `tests/test_pi_skills.py` keeps its merge-authorization rule identical to the shared skill. No source change was dispatched live. | unknown |
| 12. Recovery and handoff | `dispatch_control roll-call` listed both dispatches as `done` in the live run. Handoff and reattach are covered by the moved unit and Node tests only. | pass (roll-call); unknown live (handoff, reattach) |
| 13. Close-out | `pi/skills/reporting-to-user` is identical to the shared skill, which the tests assert; the live run reported back through intercom. | pass |
| 14. `weihung-user-claude` migration | The moved files and the three Pi skills are removed. `pi-target.py` installs straw-boss as `git:github.com/wayne930242/straw-boss` pinned at `3d0fceb` and retires any other straw-boss revision. `tests/install.sh`, `tests/uninstall.sh`, `pi_fresh_machine.py` (install and remove through the git source), `pi_port_install.py`, and `pi_review_fixes.py` pass. On this machine a full `bash scripts/install.sh` cloned the pinned commit, and the loader in `moldplan-center` then read all six skills and both extensions from it with 0 collisions. The repository was later renamed `weihung-agent-root`; its installer migrates state kept under the former name. | pass |
| 15. `moldplan-center` `work-on` hands work to `boss-say` | The diff replaces `straw-boss:boss-say` with `boss-say` and removes host-specific wording; the live run started from `boss-say`. | pass |
| 16. No skill collision in `moldplan-center` | The loader reports 56 skills and 0 collisions after `.agents/skills/*` became symlinks into the mp-infra plugin. | pass |

## Checkpoint

- First fresh-context review (`pi-host-review`, cross-family): three blockers, all caused by shared skills still directing a Pi agent to other-host mechanics, plus Pi wrap-up marking `done` before the checkpoint. These were resolved by the separate `pi/skills/` set and the `done` conditions in `pi/skills/dispatching-work` Wrap up. The two should-fix findings (`ask_user` named explicitly, pane placement in design) were applied.
- Second fresh-context review (`pi-host-review2`, cross-family): confirmed the three earlier blockers resolved and the `transport.py` default unchanged. It found one blocker: a shared checkpoint task waited for its covered tasks to be `done`, while they could not be `done` before the checkpoint. Resolved by the `delivered` state in `pi/skills/boss-say` Plan and schedule and `pi/skills/dispatching-work` Wrap up. Should-fix: the Node suites failed when run inside a Pi subagent because `PI_SUBAGENT_ID` suppresses `dispatch_control`; each suite now clears it, and the targeted tests pass with `PI_SUBAGENT_ID` set.

## Deviations

- The approved design routed Pi through sentences in the shared skills. It became a separate Pi skill set after review, the live smoke test, and the user's instruction to keep the Claude and Codex systems intact; `decision.md` records the change.
- Test-speed changes outside the spec: the `STRAW_BOSS_TRANSCRIPT_CONFIRM_POLL_INTERVAL_SECONDS` and `PI_DISPATCH_POLL_SECONDS` overrides, both keeping their production defaults, cut the suite from 184 s to 134 s.

## Gaps

- Team-mode worktree with `localFiles`, `caller_ping` round trips, dependency scheduling, and live handoff remain unexercised against a real Pi session. The first real ticket batch through `work-on` exercises the first three.
- A straw-boss change reaches Pi only after it is pushed and the pin in `weihung-agent-root/scripts/pi-target.py` is bumped.

## Reflexive

- Shared-skill routing sentences (design Approach): **misdirection**. The first design said one sentence per shared skill isolates Pi; the live run and review showed otherwise. Applied: separate `pi/skills/` set with drift tests.
- Completion-reference rule for read-only results: **misdirection**. Applied: the read-only branch in the worker contract and in `done` conditions.
- Adversarial-review owner, reviewer brief, and nit disposition: **gap**. Applied in `pi/skills/dispatching-work` Wrap up.
- Tier route location and read-only default tier: **gap**. Applied in Resolve the worker setup.
- Other-host pre-launch steps on Pi: **misdirection**. Resolved by the separate skill set, which no longer contains them.
- Roll-call format and closed panes: **gap**. Applied in Recover and hand off.
- Loading the owning skill when dispatching: **gap**. Applied in `pi/skills/boss-say` Route the work.

These were applied directly in this change's own skill text, so no separate `solid-loop` pass was run.
