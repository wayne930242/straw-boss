# Codex Herdr identity specification

## Observable behavior

- The interactive launcher waits for `agent_session.value` only for Claude.
- After the first prompt, every launch resolves the live agent and records its
  `terminal_id`; Claude additionally records and verifies its preassigned session
  id, while Codex records a null session id.
- Confirmation binds receipt pane, tab, terminal id, contract digest, and provider
  to the instruction. It never stringifies a missing session id.
- Endpoint resolution requires a session fingerprint for Claude and a terminal
  fingerprint for Codex.
- Codex live validation requires the exact pane, `agent == "codex"`, and matching
  `terminal_id`. Claude live validation remains unchanged.
- Main-agent and root-main endpoint fields carry both optional session and terminal
  fingerprints; the provider selects which one is required.
- `bash scripts/install.sh` verifies matching Claude/Codex manifest versions,
  installs or updates each available CLI adapter, and verifies the reported
  installed version. It fails when neither supported CLI is available.
- The immutable dispatch contract remains the only copy of the full task. The
  launcher sends a bounded start prompt containing `Begin contract task.` and
  `[sb256:<base64url SHA-256 digest>]`, then polls the provider-appropriate
  transcript view for that marker. The 43-character digest retains all 256
  bits. A full poll window with no match triggers exactly one resend of the same
  bounded prompt and a second poll window.
- Transcript presence checks remove all Unicode whitespace from both operands,
  tolerating terminal hard wraps and whitespace inserted inside CJK text.
- A transcript read or prompt command failure propagates immediately. Two
  successful prompt calls without transcript evidence fail launch, close the
  created pane, and write no receipt.

## Edge cases

- A missing or empty Codex terminal id fails launch or endpoint resolution.
- A Codex endpoint that resolves to Claude, another terminal id, or no live agent
  fails before a prompt is sent.
- A Claude receipt without a session remains invalid.
- A task already visible during the first poll is never resent.
- A bounded or narrow transcript view may omit the task body as long as it
  complete delivery marker after whitespace removal.
- Codex transcript reads use Herdr's visible source. Claude first uses recent
  transcript lines and falls back to visible when Herdr reports that scrolling
  requires an idle agent.
- Older Claude instruction and receipt schemas remain valid.
- Older Codex instructions without the new terminal field remain readable for
  durable state but cannot send or receive live messages.

## Compatibility constraints and non-goals

- Keep `session_id` and `main_agent_session_id` for Claude compatibility.
- Add terminal fields rather than repurposing session or Codex thread semantics.
- Do not rewrite existing contract digests or launch receipts.
- Do not infer Codex thread ids from titles, cwd, transcript text, or terminal ids.
- Keep the manual marketplace commands in both READMEs while documenting the
  checkout-local installer as the update path.

## Applied standards and precedent

- `AGENTS.md`: read before write, scoped changes, verification before success.
- `CONTEXT.md`: Herdr is the provider-neutral live transport and identity remains
  fail closed.
- `docs/specs/2026-08-25-dispatched-agent-lifecycle-transport/`: shared transport
  owns endpoint validation and provider-specific corroboration.
- Local Herdr 0.8.0 `agent list`, `agent get`, and `pane process-info` output on
  2026-08-27: Claude exposes `agent_session`; Codex exposes `terminal_id` and
  `agent: "codex"` but no session.

## Correctness strategy

The agent-operated seam is the existing public CLI suite with fake Herdr. A red
case omits `agent_session` for Codex and expects launch, receipt, confirmation,
and transport to succeed using terminal identity. Negative cases replace the
terminal id or provider and assert no prompt is sent. The focused tests are
followed by the full suite, Python compilation, manifest validation, and
`git diff --check`.

The installer is exercised as a public shell command against stateful fake
Claude and Codex CLIs for fresh-install and stale-version update paths. README
coverage asserts both languages expose the same command.

The launcher regression seam simulates a Codex TUI whose first prompt is
accepted by Herdr but absent from `agent read`; the second prompt appears in the
visible transcript. A negative case keeps both submissions absent and verifies
that no receipt survives. Another case renders a Claude transcript at 11 columns
with only six visible lines, proving the bounded marker remains confirmable.

There is no separate human appropriateness question.

## Confirmation

Confirmed on 2026-08-27 by the user's explicit delegation: "修法方向(你決定)".
The transcript-confirmation extension was confirmed the same day by the user's
explicit direction to reuse the existing reply-to-worker poll and one-retry
mechanism.
