# Dispatched-agent lifecycle and transport requirements

## Outcome and actors

Straw Boss must make a dispatched agent's lifecycle contract unavoidable at
startup and must route every cross-session message through repository scripts.
The main agent owns dispatch and coordination. A dispatched agent owns its work,
questions, checkpoints, and terminal report, but never chooses a coordinator
address itself.

## In scope

- Generate a per-dispatch contract before starting an agent.
- Inject that contract at Claude system-prompt or Codex developer-instruction
  priority on every interactive herdr launch.
- Record enough launch evidence for `dispatch-task.py confirm` to reject a
  session that did not receive the matching contract.
- Keep generated contract commands usable across plugin patch updates without
  pinning a dispatched agent to the versioned plugin-cache directory that
  created the dispatch.
- Route main-to-agent and agent-to-main messages by instruction path only.
- Validate the live receiver session against the session recorded in the
  instruction before every herdr prompt.
- When Herdr's Claude session metadata disagrees with the instruction, require
  independent agreement from the pane's foreground Claude process and Claude's
  interactive-session registry before treating the receiver as the recorded
  session.
- Keep semantic status and checkpoint commands as thin public adapters over one
  shared transport implementation.
- Prevent a dispatched Claude session from silently stopping before it writes a
  checkpoint or terminal status.
- Remove obsolete direct-routing instructions and redundant endpoint helpers.

## Out of scope

- Changing merge, push, deployment, tracker, or shared-resource authority.
- Mutating a target repository's `CLAUDE.md` or `AGENTS.md` during dispatch.
- Emulating Claude `SendMessage` or retaining it as a fallback transport.
- Treating live notification as a replacement for durable status files.
- Guaranteeing a Codex stop hook that the Codex CLI does not expose.
- Modifying Herdr's managed integration hook or server installation.
- Rebinding an instruction to whichever session Herdr currently reports.
- Rewriting an already-launched immutable contract or its launch receipt to
  retrofit dispatches created before the version-neutral launcher existed.

## Scenarios

1. A Claude or Codex agent started through the dispatch launcher receives its
   exact contract before its first model turn.
2. Confirming a dispatch without a matching launch receipt fails and leaves the
   instruction pending.
3. A worker reports `done`; the status is durable before the script notifies the
   recorded main-agent pane.
4. A worker or main agent attempts to message a pane now occupied by another
   session; the script refuses before sending.
5. A main agent replies to a checkpoint using only the instruction path; no
   pane id, session id, agent name, or provider-specific tool is supplied by the
   caller.
6. A dispatched Claude agent reaches Stop without a status report; the hook
   blocks and gives the instruction-specific reporting command. It stops normally after a valid
   status exists.
7. A herdr notification fails after a status write; the command reports the
   delivery failure while preserving durable state for watcher recovery.
8. A nested Claude SDK run overwrites Herdr's session metadata for a pane, but
   the pane's foreground interactive Claude process still owns the session
   recorded by the dispatch; transport corroborates that ownership and sends.
9. A pane is genuinely reused by another Claude session; both Herdr metadata
   and the foreground interactive Claude registry disagree with the dispatch,
   so transport refuses before prompting.
10. A long-running dispatched agent was created from an older managed plugin
    cache, then Straw Boss is updated with a transport fix; its unchanged
    contract command resolves and runs the currently enabled plugin script.

## Confirmed decisions

- The selected design is one generated contract, one launch adapter, and one
  session-validating transport seam with thin semantic wrappers.
- Contracts are immutable dispatch artifacts; the instruction records their
  path and digest, and the launch receipt binds that digest to the live session.
- Callers address both directions with an instruction path. Only the transport
  implementation reads pane and session identifiers.
- Direct `SendMessage`, direct `herdr agent prompt`, and agent-name routing are
  not public coordination paths.
- The Stop guard is a Claude lifecycle backstop. The injected contract remains
  the provider-neutral requirement for Claude and Codex.
- A Herdr mismatch is recoverable only for Claude and only through exact,
  independent foreground-process corroboration. Missing, malformed,
  non-interactive, SDK, or disagreeing evidence fails closed.
- Corroboration does not rewrite the immutable dispatch or Herdr's stored
  metadata; it authorizes only the current send after rechecking live state.
- Generated contracts invoke a version-neutral launcher under Straw Boss state.
  Managed-plugin dispatches resolve the currently enabled plugin on every call;
  source-checkout dispatches keep using their checkout. If current-plugin
  resolution is unavailable, the launcher falls back to the originating root.
- The launcher accepts only the three contract-owned communication scripts and
  never accepts an arbitrary relative or absolute script path.
- User confirmation: 2026-08-25, via the instruction to implement the proposed
  design and inspect the current architecture for redundancy.
- User requested correction of the false session-mismatch failure on
  2026-08-25 after reviewing the diagnosed Herdr metadata pollution.
- User reported the failure still appearing in long-running dispatches on
  2026-08-25; live evidence showed those agents were executing commands pinned
  to the older `0.18.0` cache after `0.18.2` was installed.

## Open questions

None.
