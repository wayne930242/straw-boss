# Agent communication contract design

## Chosen approach

Deepen the existing transport seam instead of distributing authority rules into
skills.

`send-dispatch-message.py` supplies semantic intent and optional peer metadata.
`dispatch_transport.py` resolves the expected sender and receiver from immutable
instructions, validates both live sessions, builds the trusted envelope, and
records correlation proof. `report-task-status.py` reuses sender validation
before a live task writes durable status.

The generated contract owns the compact report-content rule. `shipping-task`,
Plan mechanics, `asking-peer-agents`, and `notifying-main-agent` retain only
branch selection and the minimum command shape.

The same transport seam owns live-message economy. Callers keep one `--message`
delta and may add repeatable `--ref` values. The transport validates the
two-sentence body, renders identity/intent/correlation exactly once, and records
reference hashes rather than copying referenced material. Status reports reuse
the validator and persist their refs as structured state.

User-owned checkpoints keep their existing status names. Interactive agents wait
for the user in their own session; headless agents persist the same state so the
main agent can relay. `awaiting-main-agent` remains only for integrated direction
or coordinator-owned context/action.

Prompt authority follows an **own the loop, not the work** boundary. The main
agent chooses dispatch mechanics before launch and later observes status,
schedules dependencies, supplies cross-task facts, performs coordinator-owned
actions, and cleans up. The Herdr worker and user own the task conversation and
implementation decisions. Existing redirect/cancel transport remains compatible,
but current prompts no longer let the main agent originate a competing work
decision; it may only carry explicit user direction or protect orchestration
state.

## Interface decisions

- Keep the existing generic live-message CLI; add
  `--sender-instruction-path` and `--in-reply-to` only for peer traffic.
- Generate ids inside transport so callers cannot accidentally omit them.
- Derive sender labels from instruction data, never message prose.
- Validate `HERDR_PANE_ID` against the expected sender and reuse the existing
  session-fingerprint validator for both endpoints.
- Keep notes as strings for compatibility; reject blank notes and define their
  minimal meaning in the generated contract.
- Keep the current CLI shape and add only repeatable `--ref`; intent already
  supplies the message type, so separate question/answer/redirect scripts would
  duplicate the interface.
- Count sentence-ending punctuation for a narrow two-sentence guard. Do not add
  a character/token ceiling; overflow content belongs in a reference.
- Exempt exact slash-command control payloads from prose validation.
- Keep write-before-notify status behavior. Add explicit prompt and integration
  coverage for both terminal outcomes rather than a second Herdr state channel.

## Alternatives rejected

- Separate scripts for every intent: stronger surface separation, but more skill
  prose and adapter duplication.
- A large JSON schema for all messages: precise but disproportionate and harder
  for agents to use correctly from shell commands.
- A hard character or token budget: simple to measure but language-dependent and
  likely to reject useful paths or identifiers without improving semantics.
- Prompt-only concision guidance: smaller code change, but the existing free-text
  interface already demonstrated that agents over-explain despite prose.
- Prompt-only authority warnings: concise, but cannot prevent an incorrect peer
  from emitting a privileged-looking redirect.

## Risks and verification seam

Source authentication depends on live Herdr pane identity; headless status keeps
its compatibility path. Sentence detection is intentionally a guardrail, not a
linguistic parser; messages without terminal punctuation count as one sentence.
Public CLI tests are the primary seam because they cover argument parsing,
endpoint resolution, body/reference validation, envelope construction, and
persisted proof together.
