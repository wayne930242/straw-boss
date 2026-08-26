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

User-owned checkpoints keep their existing status names. Interactive agents wait
for the user in their own session; headless agents persist the same state so the
main agent can relay. `awaiting-main-agent` remains only for integrated direction
or coordinator-owned context/action.

## Interface decisions

- Keep the existing generic live-message CLI; add
  `--sender-instruction-path` and `--in-reply-to` only for peer traffic.
- Generate ids inside transport so callers cannot accidentally omit them.
- Derive sender labels from instruction data, never message prose.
- Validate `HERDR_PANE_ID` against the expected sender and reuse the existing
  session-fingerprint validator for both endpoints.
- Keep notes as strings for compatibility; reject blank notes and define their
  minimal meaning in the generated contract.

## Alternatives rejected

- Separate scripts for every intent: stronger surface separation, but more skill
  prose and adapter duplication.
- A large JSON schema for all messages: precise but disproportionate and harder
  for agents to use correctly from shell commands.
- Prompt-only authority warnings: concise, but cannot prevent an incorrect peer
  from emitting a privileged-looking redirect.

## Risks and verification seam

Source authentication depends on live Herdr pane identity; headless status keeps
its compatibility path. Public CLI tests are the primary seam because they cover
argument parsing, endpoint resolution, sender/receiver validation, envelope
construction, and persisted proof together.
