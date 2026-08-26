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
- A Herdr-launched dispatched agent is independent after launch. The user and
  agent own work-detail and implementation decisions; the main agent accepts
  those decisions without a second approval or competing specification.
- Questions to the main agent are limited to integrated instructions, cross-task
  context, or cases where the dispatched agent has no direct user channel.
- Main-to-worker messages carry explicit user direction, cross-task facts, or a
  coordinator-owned action result. When these conflict with a user-agent work
  decision, the main agent surfaces the conflict to the user instead of deciding.
- Every status note is non-empty. Terminal notes state outcome and verification;
  checkpoint notes state the blocker and exact unblock needed.
- Task-authoring guidance adds a concrete deliverable/proof only when not already
  clear, and parallel tasks must have distinct deliverables before sharing a
  ready wave.
- A live message body is one delta with at most two sentences. It omits identity,
  intent, correlation, repeated history, and detailed evidence already carried
  by the transport or a reference.
- `send-dispatch-message.py` and instruction-addressed status reports accept
  repeatable `--ref` values. References are delivered separately from the body;
  status JSON persists them, while the content-free delivery ledger stores only
  their count and hashes.
- Control commands are not conversational prose and retain their exact slash
  command payload.
- `done` and `failed` status reports persist first, then notify the validated
  main-agent Herdr endpoint. Notification failure remains visible and leaves the
  durable status available to the watcher.

## Compatibility and non-goals

- Existing instruction and status JSON remain readable.
- Existing transport commands keep `--instruction-path`, `--to`, `--intent`, and
  `--message`; peer calls add sender/correlation arguments and all callers may
  add references without changing existing concise calls.
- Direct user conversation is not cross-session agent messaging and does not use
  the transport script.
- No character/token limit, mandatory file list, or duplicated lifecycle
  checklist is introduced. Sentence validation is deliberately narrow.

## Applied standards

- [Anthropic multi-agent research](https://www.anthropic.com/engineering/multi-agent-research-system): objective, output, source guidance, and boundaries.
- [Claude Code agent teams](https://code.claude.com/docs/en/agent-teams): enough task context and non-overlapping parallel work.
- [OpenAI Agents SDK handoffs](https://openai.github.io/openai-agents-python/handoffs/): structured handoff metadata and filtered context.
- [Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents): smallest high-signal context and direct language.
- [A2A specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md): separate messages, status, and artifacts.
- [AutoGen stateful agents](https://microsoft.github.io/autogen/stable/reference/python/autogen_agentchat.agents.html): pass only new messages rather than full history.
- `writing-great-skills`: one source of truth, aggressive pruning, positive rules.

## Correctness strategy

Public CLI integration tests with fake Herdr sessions prove sender refusal,
allowed sends, peer round-trip correlation, two-sentence rejection, structured
references, content-free delivery records, and status-note validation.
Source-contract tests keep skills concise and ensure the delta-only rule is
stated once. Terminal integration tests cover successful `done` and `failed`
Herdr notifications. Run the focused and full unittest suites plus Python
compilation.

## Human appropriateness

No later checkpoint is required. The user supplied the criterion: preserve the
behavior while simplifying skill prompts.

## User confirmation

Confirmed on 2026-08-26 in this conversation, including delta-only messages,
independent Herdr workers, and terminal notification to the main agent.
