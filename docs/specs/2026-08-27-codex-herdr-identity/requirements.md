# Codex Herdr identity requirements

## Outcome and actors

Interactive Codex workers launched through Herdr 0.8.0 must complete launch,
confirmation, coworker derivation, and live transport without depending on the
Claude-only `agent_session` field. Claude workers retain their existing session
fingerprint checks.

Actors are the main agent, the dispatched Claude or Codex worker, Herdr, and the
provider CLIs.

## In scope

- Provider-specific worker and coordinator identity in dispatch instructions,
  launch receipts, confirmation, and shared transport.
- Codex launch without polling `agent_session.value`.
- A Herdr-observable Codex fingerprint that detects a different terminal or
  provider in the recorded pane.
- Same-worktree coworker endpoint derivation for Claude and Codex parents.
- Current dispatch guidance and regression coverage.
- A repo-owned, repeatable local installer for the Claude and Codex plugin
  adapters, documented in both READMEs.

## Out of scope

- Extracting a Codex thread id from terminal output or Codex internal storage.
- Implementing `codex exec resume` for interactive Herdr workers.
- Changing Herdr itself or rewriting historical immutable contracts.
- Hosted releases or tags.

## Scenarios

1. A Codex worker starts and becomes idle without `agent_session`; launch records
   its pane, tab, terminal id, and agent kind and returns without a timeout.
2. Confirmation copies the Codex terminal fingerprint without converting a JSON
   null session into the string `"None"`.
3. A Codex sender or receiver passes live transport only when Herdr reports the
   recorded pane, terminal id, and Codex agent kind.
4. A replaced terminal or different provider in the pane fails closed.
5. Claude launch and transport continue to require the exact session id, including
   the existing foreground-process corroboration path.
6. A Codex parent can create one coworker using its terminal fingerprint; root
   coordinator identity remains provider-specific.
7. From a source checkout, `scripts/install.sh` installs or updates Straw Boss
   for every locally available supported CLI and verifies the installed version.

## Confirmed decisions

- `agent_session.value` is a Claude identity source, not a provider-neutral one.
- Codex live Herdr identity uses `pane_id + terminal_id + agent kind`.
- Codex provider thread id is a separate future field and must not be fabricated
  from Herdr terminal metadata.
- Existing Codex instructions without a terminal fingerprint fail closed for live
  transport and require a fresh dispatch.
- The user delegated the repair choice on 2026-08-27.

## Open questions

None.
