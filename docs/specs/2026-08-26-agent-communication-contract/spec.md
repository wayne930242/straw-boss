# Agent communication contract specification

## Observable contract

- Every live send validates both the current sender pane/session and the recorded
  receiver pane/session before prompting.
- Worker-to-main accepts question, inform, and status. Main-to-worker accepts
  inform, redirect, reply, and control. Peer-to-worker accepts question and
  answer only and requires the sender's instruction path.
- Peer messages contain a transport-generated message id, verified sender label,
  and return instruction path. An answer is accepted only when `in_reply_to`
  matches a recorded question between the same two live sessions.
- Delivery records retain correlation and endpoint proof without message text.
- A live dispatched agent may write only its own status. `cancelled` remains a
  main-agent operation. Headless status compatibility is unchanged.
- Interactive `awaiting-user-input` and `awaiting-authorization` checkpoints are
  answered directly by the user in the dispatched agent's session. For a
  headless agent, the main agent relays without deciding for the user.
- Questions to the main agent are limited to integrated instructions, cross-task
  context, or cases where the dispatched agent has no direct user channel.
- Every status note is non-empty. Terminal notes state outcome and verification;
  checkpoint notes state the blocker and exact unblock needed.
- Task-authoring guidance adds a concrete deliverable/proof only when not already
  clear, and parallel tasks must have distinct deliverables before sharing a
  ready wave.

## Compatibility and non-goals

- Existing instruction and status JSON remain readable.
- Existing transport commands keep `--instruction-path`, `--to`, `--intent`, and
  `--message`; peer calls add sender/correlation arguments.
- Direct user conversation is not cross-session agent messaging and does not use
  the transport script.
- No prompt length limit, prose linter, mandatory file list, or duplicated
  lifecycle checklist is introduced.

## Applied standards

- [Anthropic multi-agent research](https://www.anthropic.com/engineering/multi-agent-research-system): objective, output, source guidance, and boundaries.
- [Claude Code agent teams](https://code.claude.com/docs/en/agent-teams): enough task context and non-overlapping parallel work.
- [OpenAI Agents SDK handoffs](https://openai.github.io/openai-agents-python/handoffs/): structured handoff metadata and filtered context.
- `writing-great-skills`: one source of truth, aggressive pruning, positive rules.

## Correctness strategy

Public CLI integration tests with fake Herdr sessions prove sender refusal,
allowed sends, peer round-trip correlation, content-free delivery records, and
status-note validation. Source-contract tests keep skills concise and ensure the
new guidance is stated once. Run the focused and full unittest suites plus Python
compilation.

## Human appropriateness

No later checkpoint is required. The user supplied the criterion: preserve the
behavior while simplifying skill prompts.

## User confirmation

Confirmed on 2026-08-26 in this conversation.
