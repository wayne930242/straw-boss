## 1. Roles reference document

- [x] 1.1 Write `docs/roles.md` from `CONTEXT.md` — cast of characters, the "boss"-in-identifiers naming rule, the inform/redirect/cancel authority model, and the autonomy boundary (including the dispatched-agent-failure-reporting-is-unaffected clarification)

## 2. Skill context pointers

- [x] 2.1 Add a `docs/roles.md` context pointer to `boss-say/SKILL.md`'s Overview
- [x] 2.2 Add a `docs/roles.md` context pointer to `dispatching-work/SKILL.md`'s Overview
- [x] 2.3 Add a `docs/roles.md` context pointer to `work-on/SKILL.md`'s Overview
- [x] 2.4 Add a `docs/roles.md` context pointer to `shipping-task/SKILL.md`'s Overview
- [x] 2.5 Add a `docs/roles.md` context pointer to `inspecting-app/SKILL.md`'s Overview
- [x] 2.6 Add a `docs/roles.md` context pointer to `investigating-app/SKILL.md`'s Overview
- [x] 2.7 Add a `docs/roles.md` context pointer to `troubleshooting-app/SKILL.md`'s Overview

## 3. Rename `notifying-boss` to `notifying-main-agent`

- [x] 3.1 Rename the `skills/notifying-boss/` directory to `skills/notifying-main-agent/` and update its own `SKILL.md` name/description/prose to match
- [x] 3.2 Add the `docs/roles.md` context pointer to `notifying-main-agent/SKILL.md`'s Overview
- [x] 3.3 Update `shipping-task` Task 4's dispatch-instruction-building text to reference `notifying-main-agent`
- [x] 3.4 Update `docs/architecture.md`'s Components table entry for the renamed skill
- [x] 3.5 Update every reference in `dispatching-work/references/cross-session-coordination.md`
- [x] 3.6 Grep the repo for any remaining `notifying-boss` references and fix them

## 4. Name and document inform/redirect

- [x] 4.1 In `cross-session-coordination.md`, name and document the existing non-interrupting `herdr agent prompt` queue behavior as `inform`
- [x] 4.2 In `cross-session-coordination.md`, apply the canonical name `redirect` to the existing "Mid-task interrupt and correction" mechanism

## 5. Implement `cancel` and the `cancelled` status

- [x] 5.1 Add `cancelled` as a recognized terminal status in `plan-mechanics.md`'s status-file schema documentation, alongside `done`/`failed`
- [x] 5.2 Update `scripts/read-plan-status.py` so `--in-flight`/`--ready`/`--not-done` all treat `cancelled` as terminal
- [x] 5.3 Update `scripts/wrap-up-task.py` to accept `cancelled` alongside `done`/`failed` when archiving a task
- [x] 5.4 Update the `Monitor` polling-loop guidance in `plan-mechanics.md` to emit on `cancelled` the same way it does for `done`/`failed`/`awaiting-*`
- [x] 5.5 Document `cancel` mechanics for `herdr-pane` in `cross-session-coordination.md` (interrupt, close pane/tab/worktree without expecting further output, write `cancelled` to the status file)
- [x] 5.6 Document `cancel` mechanics for `claude-p` in `cross-session-coordination.md` (`TaskStop` the backgrounded process, write `cancelled` to the status file, discarding whatever it was mid-way through) — reusing the mechanism already documented for an undeliverable redirect, not new

## 6. Red Flags mechanical pass

- [x] 6.1 Audit `boss-say/SKILL.md`'s Red Flags entry-by-entry against `docs/roles.md`: fold in and delete where the content can be phrased positively there, otherwise keep paired with its positive target — audited clean, all 12 are batch/dispatch mechanics unrelated to roles/naming/authority, none folded
- [x] 6.2 Audit `dispatching-work/SKILL.md`'s Red Flags the same way — audited clean, all 17 are dispatch-mode/worktree/resource-lock mechanics, none folded
- [x] 6.3 Audit `work-on/SKILL.md`, `shipping-task/SKILL.md`, `inspecting-app/SKILL.md`, `investigating-app/SKILL.md`, `troubleshooting-app/SKILL.md`, and `notifying-main-agent/SKILL.md`'s Red Flags the same way — one fold: `shipping-task`'s "agent can close out the ticket itself" → the tracker-ticket-mutation sentence added to `docs/roles.md`'s Autonomy boundary; every other entry audited clean

## 7. Restructure `docs/architecture.md`

- [x] 7.1 Restructure the Components table to point at `docs/roles.md` for role definitions instead of duplicating role prose inline

## 8. Validation

- [x] 8.1 Run `openspec validate --strict --change establish-roles-and-authority`
- [x] 8.2 Grep the repo for any remaining prose use of "boss" meaning the main agent (outside the now-correct `boss-say` identifier) and fix — clean, none found
