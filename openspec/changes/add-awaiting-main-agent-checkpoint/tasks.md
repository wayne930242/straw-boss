## 1. Status plumbing

- [x] 1.1 Add `awaiting-main-agent` to `VALID_STATUSES` in `scripts/report-task-status.py`.
- [x] 1.2 Update `scripts/wrap-up-task.py`'s two hardcoded refusal-message strings ("...still awaiting authorization or user input") to also name `awaiting-main-agent` — no logic change, the existing `status not in ("done", "failed", "cancelled")` membership check already refuses it correctly.

## 2. `reply-to-worker.py`

- [x] 2.1 Create `scripts/reply-to-worker.py` with `--worker-instruction-path` and `--reply` arguments; read the worker's instruction file and refuse (non-zero exit, clear stderr message) if its `mode` isn't `herdr-pane`.
- [x] 2.2 Resolve the worker's own status-file path, reusing the same plan-task-vs-standalone resolution logic `report-task-status.py`'s `resolve_status_path` already implements; refuse if the current `status` isn't `awaiting-main-agent`.
- [x] 2.3 Shell out to `herdr agent get "<herdr_pane_id>"` to resolve the worker's current live addressable name; refuse if the pane/agent no longer exists (mirroring `asking-peer-agents`' Task 4 step 1-2 liveness check).
- [x] 2.4 Shell out to `herdr agent prompt "<name>" "<reply>"` (no `--wait` — see task 8.1 for why), then confirm delivery with a short bounded poll of `herdr agent read "<name>" --lines 500` (task 8.5) checking the reply text reached the transcript (whitespace-normalized — task 9.2). Retry the send once if a full poll window never confirms it; fail loudly (non-zero exit, status file untouched) if still unconfirmed after the retry.
- [x] 2.5 On confirmed delivery, read-modify-write the status JSON to add `resolved_by_main_agent_at` (timestamp) and `main_agent_reply` (the sent text) fields, preserving the existing `status`/`note`/`timestamp` fields unchanged; print success.

## 3. Skill and reference doc updates

- [x] 3.1 `skills/dispatching-work/SKILL.md`: add an `awaiting-main-agent` row to the "Four checkpoint/report types" table (For: blocked pending an action only the main agent's own judgment/authority can take; Answered by: the main agent itself, via `reply-to-worker.py`, no human needed; Terminal?: No — main agent resolves, worker continues on its own once resumed).
- [x] 3.2 `skills/dispatching-work/SKILL.md`: add a Red Flag warning against resolving this checkpoint any way other than `reply-to-worker.py` (e.g. replying only in reasoning, or manually running `herdr agent prompt` without the confirm-and-record step).
- [x] 3.3 `skills/dispatching-work/references/plan-mechanics.md`: add `awaiting-main-agent` to the `Monitor` loop's watched-status list in "Monitoring completion", and document its on-detection handling — the main agent resolves it itself via `reply-to-worker.py`, unlike `awaiting-user-input`'s "tell the user which pane to answer in."
- [x] 3.4 `skills/notifying-main-agent/SKILL.md`: add guidance distinguishing the existing fire-and-forget informational-question branch (doesn't block progress) from the new `awaiting-main-agent` checkpoint (genuinely blocks progress until the main agent acts) — including that it's reported the same way as the other checkpoints (`report-task-status.py --status awaiting-main-agent`, then the required `SendMessage` push).
- [x] 3.5 `skills/notifying-main-agent/SKILL.md`: add a Red Flag distinguishing "this is just a question I can keep working around" (informational channel) from "I am genuinely stuck until the main agent acts" (`awaiting-main-agent`).

## 4. Spec consistency

- [x] 4.1 Run `openspec validate --strict` (or the project's equivalent) against the change and confirm the three spec deltas apply cleanly.
- [x] 4.2 Cross-check every file listed in `proposal.md`'s Impact section was actually touched by tasks 1-3.

## 5. Manual verification

- [x] 5.1 Exercise `reply-to-worker.py` end-to-end against a synthetic herdr-pane dispatch whose status file reads `awaiting-main-agent`, via a mocked `herdr` CLI: happy path (lookup → send → poll-confirm → status-update), refusal paths (wrong mode, wrong current status, pane no longer live), schema-mismatch (fails immediately, no resend), never-confirmed-after-retry (exactly 2 sends, hard fail), and a busy-worker scroll-out case (200 lines of new output after the reply, must confirm without resending). All confirmed against the mock.
- [x] 5.1b **Closed — real herdr session, both items resolved a real bug each (see group 9).** `herdr agent get`'s `.result.agent.name` confirmed correct as-is. `herdr agent read` turned out to have no JSON mode at all (found and fixed, task 9.1). The long/multi-line-reply check found a genuine false-negative-then-resend from line-wrapping (found and fixed, task 9.2) — the worker executed the same reply twice before the fix landed.
- [x] 5.2 Confirm `wrap-up-task.py` still refuses to archive a task both before and after `reply-to-worker.py` has run against it (since `status` deliberately stays `awaiting-main-agent` until the worker itself later reports a terminal status), and succeeds only once the worker reports `done`/`failed`. Verified end-to-end in an isolated `$HOME`: refuses before reply, still refuses after a successful reply, succeeds once a simulated `report-task-status.py --status done` write lands.

## 6. Instruction-assembly reachability (found during review — without this, nothing can ever produce `awaiting-main-agent`)

- [x] 6.1 `plan-mechanics.md`'s plan-task instruction-assembly item list: add the item stating a worker must be told this checkpoint exists, mirroring the existing `awaiting-user-input` item.
- [x] 6.2 `shipping-task/SKILL.md` Task 4 (assembles a *standalone* dispatch's instruction, a separate path from plan-task assembly): add the same statement, plus a Task 5 paragraph on how this skill responds (resolves directly via `reply-to-worker.py`, unlike `awaiting-user-input` which it explicitly leaves alone).
- [x] 6.3 `boss-say/SKILL.md` Task 5: add a step that resolves an `awaiting-main-agent` finding inline, in the same tick — distinct from step 5's "leave `awaiting-authorization`/`awaiting-user-input` alone and report" handling, since this checkpoint isn't waiting on the user. Renumbered and fixed the four stale "step 6" cross-references the insertion shifted.
- [x] 6.4 `docs/roles.md`: add a fourth main-agent authority action, `Resolve`, alongside Inform/Redirect/Cancel — `dispatch-authority`'s spec delta already required this action exist; the prose authority framework didn't yet name it.

## 7. Correctness and prose pass (from advisor review)

- [x] 7.1 Fix `reply-to-worker.py`'s retry logic: an unrecognized `herdr agent read` response shape now raises immediately (no resend) instead of being silently treated as "not confirmed" — the guessed field names (`transcript`/`text`) were never verified against a live session, and the original logic would have resent on every call if the guess was wrong, regardless of whether the first send actually landed.
- [x] 7.2 Trim the prose added across all touched skill/reference files: cut restated rationale that duplicates `design.md`, collapse redundant Red Flags, shorten cross-file duplication of the escalation order (stated once in `plan-mechanics.md`, pointed to elsewhere) — situational and concise over exhaustive, matching this codebase's own skill-writing conventions.
- [x] 7.3 Bring `proposal.md`/`design.md` back in sync with the actual diff: Impact section now lists every touched file (task 6's additions weren't in the original list), Goals no longer claims zero behavior change when a pre-existing inaccuracy in `notifying-main-agent` was corrected along the way.

## 8. Confirmation-timing fix (second advisor pass — this one blocked, the mock hid it)

- [x] 8.1 Drop `--wait`/`--timeout` from `send_reply`'s `herdr agent prompt` call. `--wait` blocks until the worker's *whole turn* ends, not until the message is delivered — but the resumed worker may then do real, possibly long-running work (redispatch a dependency, resolve a conflict), so a successful delivery would routinely time out and get reported as a failure.
- [x] 8.2 Replace the single instant `herdr agent read` confirmation with a short bounded poll (`CONFIRM_POLL_ATTEMPTS` × `CONFIRM_POLL_INTERVAL_S`) — without `--wait`, an instant read right after sending can run before the transcript even registers the submission, which would otherwise trigger a spurious resend on every call.
- [x] 8.3 Relax `reply_landed` to presence-only (the reply text reached the transcript), dropping the "content must follow it" requirement carried over from `dispatch-mechanics.md` step 6.5's fresh-pane dispatch case — requiring visible worker output afterward reintroduces the same timing trap `--wait` had, just inside the confirmation check instead of the send.
- [x] 8.4 Re-verify all paths against the mocked `herdr` CLI after the redesign: happy path, confirmation landing only on a later poll attempt (must NOT resend), schema-mismatch (must fail immediately, no polling, no resend), and never-confirmed-after-retry (exactly 2 sends, hard failure, status untouched). All four confirmed.
- [x] 8.5 Widen `CONFIRM_READ_LINES` from 40 to 500 (third advisor pass): presence-only confirmation against a *fixed tail* has the same failure shape as the `--wait` bug it replaced — a busy worker producing enough output scrolls the reply out of a narrow window, and the poll window exhausting then triggers a resend into a pane that's actively executing the first one. Verified against a mock producing 200 lines of worker output after the reply: confirms on the first poll, exactly one send.
- [x] 8.6 `confirm_landed`: skip the final `time.sleep` after the last poll attempt fails — cosmetic, saves one interval per failed window.

## 9. Live herdr verification (task 5.1b — two real bugs found and fixed against an actual session, not a mock)

- [x] 9.1 **`herdr agent read` has no JSON output mode** (`--format` is only `text`/`ansi`) — confirmed live: the version of the script that existed at this point called the same JSON-parsing helper used for `agent get`/`agent prompt`, which raised a JSON decode failure on every real `agent read` call, before ever reaching the confirmation logic. Fixed: `agent read` now goes through a separate raw-stdout path (`run_herdr_raw`); `run_herdr` (JSON) stays for `agent get`/`agent prompt` only. `.result.agent.name` confirmed correct against a real pane in the same pass.
- [x] 9.2 **Line-wrapped replies broke exact substring matching — reproduced a real duplicate send.** A long reply hard-wraps at the pane's column width in `agent read`'s rendering; the space at the wrap point becomes a newline, so `transcript.rfind(reply)` doesn't find it even though the reply landed. Confirmed live: this caused the script to retry, and the throwaway test worker executed the identical reply a second time — the exact non-idempotent double-send this whole feature was built to prevent. Fixed: `reply_landed` now compares with all whitespace runs collapsed to a single space on both sides.
- [x] 9.3 Set up an isolated throwaway herdr tab/pane (`herdr tab create` + `herdr agent start`) for live testing rather than touching any of the user's real dispatched sessions; closed the tab and removed the scratch instruction/status fixture afterward.
- [x] 9.4 Re-ran the full script against the live pane after both fixes, twice, with two different long reply texts (one deliberately re-sent, one brand new) — both confirmed correctly, exactly one send each, `CONFIRM_READ_LINES=500` separately confirmed live (task 8.5's mock-only claim now has a live match: original prompt findable after 80 lines of new output).
