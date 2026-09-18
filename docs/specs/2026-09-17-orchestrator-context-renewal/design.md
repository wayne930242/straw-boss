# Design: context renewal

Spec: [spec.md](spec.md). Decisions: [decision.md](decision.md).

## Prototype results (2026-09-17, Herdr pane in a scratch workspace)

| Question | Claude Code 2.1.274 | Codex 0.154.0 | Antigravity 1.2.5 |
|---|---|---|---|
| Self-clear after the turn ends | A process detached with `start_new_session=True` runs `herdr agent wait <pane> --until idle --until done`, then `herdr agent prompt <pane> /clear`. Delivered. | Same; a plain `nohup … &` from the shell tool is killed with the turn, `start_new_session` survives. Delivered. | Same. Delivered. |
| SessionStart after the clear | Fires at once, `source: "clear"`, new `session_id`. | Fires on the new thread's first turn, `source: "clear"`, new `session_id`. | Fires on the new conversation's first turn, new `conversationId`, no `source` field. |
| Injection | Hook stdout reaches the model. | Hook stdout reaches the model. | Stdout is decoded as the SessionStart result; `{"injectSteps":[{"ephemeralMessage":"<text>"}]}` reaches the model (plain text is rejected). |
| Stop hook blocks the turn end | `{"decision":"block","reason"}` | `{"decision":"block","reason"}` | `{"decision":"block","reason"}` in named-hook format. |
| Context measure | `transcript_path` → last assistant `message.usage`: `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`. | `transcript_path` → last `token_count` event `info.last_token_usage.input_tokens` (includes cached). | `~/.gemini/antigravity-cli/conversations/<conversationId>.db`, last `gen_metadata` row, protobuf fields `1.4.2` (uncached input) + `1.4.5` (cached input). Undocumented; the transcript carries no counts. |

Agy finding: agy rejects the Claude-format root `hooks.json` ("command hook must specify 'command'"), so today neither priming nor the stop guard runs under agy. Agy's plugin hooks use the named format `{"<name>": {"enabled": true, "<Event>": [{"type": "command", "command": …}]}}`.

No provider fails measure, self-clear, or inject, so the spec stands. The agy measure reads an undocumented store; a format change there makes agy report no measure and skip renewal (backstop is absent for agy, see Risks).

## Approach

Deterministic trigger in hooks, judgment in the model, delivery in a detached process.

1. **Stop hook** `scripts/context-renewal-guard.py` (registered after the stop guard in `hooks/hooks.json` and the agy `hooks.json`):
   - Reads the provider payload, measures context. At or below 200k: allow.
   - This pane already has a pending record from this session: allow (renewal is scheduled).
   - This session was itself started by a renewal and is still above 200k: allow, printing the one-time report (edge case "starts above 200k").
   - Otherwise block once with a reason naming `renew-context.py` and the role/payload it needs. A second stop in the same session without a record allows (loop guard: `stop_hook_active`, or a per-session marker for agy).
2. **Model runs** `scripts/renew-context.py --role <main-agent|dispatched-worker|standalone-worker> [--instruction-path …] ` with the continuity payload on stdin:
   - Writes `~/.straw-boss/renewal/<pane>.json`: `pane_id`, `agent_kind`, `session_id` (the renewing session), `role`, `payload`, `instruction_paths`, `created_at`, `status: pending`.
   - A dispatched worker also appends a progress note (`report-progress.py` path) naming the record.
   - Prints the one-line notice with the record path.
   - In Herdr: spawns detached `scripts/deliver-renewal.py <pane>` that waits for idle/done, sends the provider clear command (`/clear` on all three), waits for the cleared composer, and prompts `Continue from the context renewal record.` so Codex and agy fire SessionStart. Outside Herdr the notice asks the user to run `/clear`.
3. **SessionStart** `scripts/orchestrator-priming.py` checks `HERDR_PANE_ID` first:
   - A pending record for this pane, same `agent_kind`, whose `session_id` differs from the hook's session: consume it (`status: consumed`, `consumed_by`), adopt, and print role priming + the record.
   - Otherwise today's behavior unchanged (behavior 11, and "clear with no pending record").
   - Under agy the text is wrapped as `injectSteps` / `ephemeralMessage`.
4. **Adoption in the hook** (`scripts/straw_boss/renewal.py`), proven by `validate_current_process_in_pane(pane)` and by the instruction still naming the record's session in this pane:
   - Main agent: `main_agent_session_id` rewritten for instructions whose `main_agent_herdr_pane_id` is this pane and whose recorded session is the record's; appended to `main_agent_adoptions`. The orchestrator record keyed on the old fingerprint is re-keyed to the new session with the same scope.
   - Dispatched worker: `session_id` rewritten for instructions whose worker pane is this pane; appended to `worker_adoptions`.
   - Agy identity is terminal-only when no session is recorded, so nothing is rewritten.
   - Standalone worker: no instruction, no adoption.
   - Main agent and dispatched worker: the hop is appended to `renewal/lineage.jsonl` and the old session's orchestrator message ledger moves to the new key; peer-reply validation accepts any session in a lineage.
5. **Priming by role**: main agent → orchestrator stance + record; dispatched worker → its contract + record; standalone worker → record only. Only the main agent gets main-agent priming.
6. **Stop guard**: `dispatched-agent-stop-guard.py` also accepts a pending renewal record from the stopping session, so the worker's turn ends without a fake status (the progress note is the checkpoint the spec names; status file format unchanged).
7. **Agy hooks**: root `hooks.json` converted to the named format, which also restores priming and the stop guard under agy.

## Interfaces touched

- New: `scripts/straw_boss/renewal.py` (measure, record I/O, adoption), `scripts/context-renewal-guard.py`, `scripts/renew-context.py`, `scripts/deliver-renewal.py`.
- Changed: `scripts/orchestrator-priming.py`, `scripts/dispatched-agent-stop-guard.py`, `hooks/hooks.json`, `hooks.json`, `skills/i-am-orchestrator/SKILL.md` and dispatched-worker contract text (one short section each naming renewal), version manifests.
- Unchanged: dispatch contracts, status file formats, `handoff-orchestrator`.

## Precedent

- `adopt-dispatch.py`: pane-proven adoption with an audit trail.
- `cross-session-coordination.md` "Main-agent self-compact": a session submits a command to its own pane.
- `orchestrator-priming.py`: role-aware SessionStart output.

## Risks

- Agy measure depends on an undocumented protobuf; tests pin the decoding against a captured row.
- A user message typed into the composer while the clear is pending may merge with `/clear`; the live run checks behavior 9 and the deliverer only sends when Herdr reports idle/done.
- Codex hooks need user trust once after install (existing Codex behavior).

## Reality anchor method

1. Unittest: measurement per provider from fixture payloads/transcripts/DB rows; guard decisions; record write/consume once; pane mismatch never injects; role priming; worker and main adoption; stop-guard acceptance.
2. Live Herdr run per provider as the spec names, driven through `herdr agent prompt` and `herdr pane read`; sessions exceed 200k by reading large files.

## Friction Notes

- Tried: `nohup sh -c '…' &` from Codex's shell tool to deliver `/clear`.
  Found: Codex kills the tool's process group when the turn ends; a `start_new_session` child survives.
  Led by: none
- Tried: running agy with `STRAW_BOSS_PLUGIN_ROOT` to intercept straw-boss hooks.
  Found: agy never parses the Claude-format root `hooks.json`; plugin hooks need the named format.
  Led by: none
- Tried: reading agy context size from `transcript_full.jsonl` and hook payloads.
  Found: neither carries token counts; only the conversation DB `gen_metadata` does.
  Led by: decision.md "provider-specific context measurement … settled in Design"
- Tried: plain-text SessionStart stdout under agy, judged by the model repeating the injected word.
  Found: agy rejects non-JSON results in cli.log; the model had read the hook script itself. Only a side effect or cli.log proves injection.
  Led by: none
- Tried: sending `/effort low` to a live Claude test session.
  Found: it persists `modelSettings.<model>.effortLevel` into the user's global settings.
  Led by: none
