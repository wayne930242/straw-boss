# Pi host support — design

Spec: [spec.md](spec.md).

## Approach

Pi gets its own set of the six workflow skills under `pi/skills/`, with the same names, so every file under `skills/` stays byte-identical for Claude Code, Codex, and Antigravity. The Pi set keeps the workflow text and replaces each mechanic with a Pi tool, plain git, or a direct file read. The first draft routed Pi through one sentence in each shared skill; review and the live smoke test showed a Pi agent still reading host-specific steps there, and the user asked for isolation, so the Pi set replaced it.

## Files

| Path | Change |
|---|---|
| `package.json` | New. `pi.skills` lists the six `pi/skills/` directories; `pi.extensions` lists the two extensions. |
| `pi/skills/dispatching-work/SKILL.md` | Pi mechanics: worker setup, checkout, brief and worker contract, launch, events, wrap-up, recovery, handoff. |
| `pi/skills/{boss-say,work-on,choosing-graph,shipping-task}/SKILL.md` | Pi versions of the shared skills: same policy, Pi mechanics and links. |
| `pi/skills/reporting-to-user/SKILL.md` | Identical copy of the shared skill; its links resolve inside the Pi set. |
| `pi/extensions/dispatch-recovery.ts`, `pi/extensions/pane-balance.ts`, `pi/scripts/pi-dispatch.py`, `pi/package.json` | Moved from `weihung-user-claude`; the helper path becomes `../scripts/pi-dispatch.py`; `pi/package.json` marks the extensions as ES modules for Node. |
| `tests/pi/*.mjs`, `tests/test_pi_dispatch.py` | Moved extension and helper tests, plus a runner for the Node suites. |
| `tests/test_pi_package.py` | Manifest exact-set test and a resolution test through Pi's `DefaultPackageManager`. |
| `tests/test_pi_skills.py` | The Pi set carries no other-host mechanics, its links resolve, it is English, and its shared policy matches `skills/`. |
| `README.md`, `README.zh-TW.md`, `docs/architecture.md` | Pi listed as a host with its install line. |
| version files | 0.31.0, `package.json` included. |

## Data flow on Pi

`boss-say` → `work-on` (direct JSON read) → `choosing-graph` → `shipping-task` mode → `dispatching-work`: tier, checkout, brief, `subagent` → `dispatch-recovery.ts` records the launch → `subagent_result` / `caller_ping` / stall notice wake the main agent → `dispatching-work` events and wrap-up → `reporting-to-user`.

## Precedent

- Worktree creation and removal use the plain-git commands of the shared [Worktree ownership](../../../skills/dispatching-work/references/plan-mechanics.md#worktree-ownership).
- The ledger, handoff, and delivery behavior is the tested `weihung-user-claude` implementation, moved without behavior change.

## Trade-offs and risks

- Two skill sets duplicate policy text; `tests/test_pi_skills.py` fails when the shared policy terms drift apart, and `reporting-to-user` must stay identical.
- `subagent`'s own `worktree` option is not used, so `localFiles` are in place before the worker starts and cleanup stays one `git worktree remove`. `pi-herdr-agents` places the pane in the Herdr workspace that owns the checkout, or the caller's workspace when none does.
- Undispatched dependents live only in the todo list and handoff summary; a crash of the main process loses them unless the user restarts the round. Accepted in Q4.
- The resolution test depends on a local Pi installation and skips without one; the exact-set test always runs.

## Friction Notes

- Tried: marking a read-only dispatch done by the completion-reference rule in the Pi mechanics reference (now `pi/skills/dispatching-work`) Handle events.
  Found: an investigation returns an explanatory result with evidence references and no commit, so the rule marked a correct result failed; the worker contract also asked read-only workers for a commit and review disposition.
  Led by: the Pi mechanics reference (now `pi/skills/dispatching-work`) Handle events and Write the brief (live smoke test, `sb-pi-smoke`).
- Tried: running the adversarial-review checkpoint for a single read-only dispatch.
  Found: the Pi mechanics reference (now `pi/skills/dispatching-work`) named no owner or launch for that checkpoint; the smoke session substituted a main-agent citation check.
  Led by: the Pi mechanics reference (now `pi/skills/dispatching-work`) Wrap-up on Pi.
- Tried: resolving the worker tier from "a root `AGENTS.md` work route".
  Found: three `AGENTS.md` files are in scope on Pi and their routes name skills, so "root" was ambiguous.
  Led by: the Pi mechanics reference (now `pi/skills/dispatching-work`) Resolve the worker setup.
- Tried: following `dispatching-work` Prepare the dispatch on Pi.
  Found: its Herdr, registration, and fingerprint steps have no Pi counterpart and the Pi mechanics reference (now `pi/skills/dispatching-work`) did not say they are replaced.
  Led by: `skills/dispatching-work/SKILL.md` Prepare the dispatch.
- Tried: reading a finished dispatch's pane from `dispatch_control roll-call`.
  Found: the pane had closed (`pane_not_found`); roll-call prints the ledger's last-known pane in an undocumented `id | status | name | pane | session` format.
  Led by: the Pi mechanics reference (now `pi/skills/dispatching-work`) Recover and hand off.
- Tried: routing Pi through one "On a Pi host" sentence in each shared skill.
  Found: a Pi agent still read the other hosts' scripts, plan files, and pre-launch checks in those skills, and every Pi fix touched files the other hosts load.
  Led by: the first draft of this design's Approach.
- Tried: a second live smoke test (`sb-pi-smoke2`) with the separate Pi skill set.
  Found: the flow ran end to end, including a fresh review subagent for the adversarial-review checkpoint; remaining ambiguity was whether to load the owning skill when dispatching, which `AGENTS.md` holds a tier route, the `coding` default for read-only work, and the reviewer's brief and nit disposition.
  Led by: `pi/skills/boss-say` Route the work and `pi/skills/dispatching-work` Resolve the worker setup and Wrap up.
