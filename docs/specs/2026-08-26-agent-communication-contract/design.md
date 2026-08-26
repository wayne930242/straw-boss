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
schedules dependencies, assigns the user requirement and requested outcome,
supplies necessary integrated context, performs coordinator-owned actions, and
cleans up. The Herdr worker and user own the task conversation, specification,
design, implementation, and verification method. Existing redirect/cancel
transport carries explicit user direction and protects orchestration state.

Pane placement moves behind the existing launch adapter. The instruction already
contains the validated main-agent pane and target `repo_root`, so the launcher
needs no placement arguments: it gets the main pane, splits a right-hand pane
with the target cwd, verifies the returned `tab_id` matches the main pane, and
records both identities in the receipt. This centralizes the invariant and
deletes tab lifecycle knowledge from dispatch callers.

Coworking reuses that adapter without recursively granting the orchestrator
stance. A narrow `dispatch-coworker.py` facade authenticates the current worker
from its instruction, then drives the existing write, launch, and confirm public
interfaces. `dispatch-task.py write --parent-instruction-path` derives all
placement and identity fields from the parent instruction and rejects a second
nesting level or a different worktree. The child stores its root coordinator as
a second status-only endpoint.

Codex contract injection changes from value transport to path indirection. The
launcher gives Codex one short developer-priority instruction to read the
immutable contract file before acting. This keeps the contract at developer
priority while removing multiline quotes and backticks from the Herdr
target-shell argument seam.

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
- Replace launcher `--pane-id`/`--tab-id` with instruction-derived placement.
  Keep `dispatch-task.py confirm` receipt-driven and backward-readable.
- Close only worker panes at terminal state. The shared tab is coordinator-owned
  and remains open.
- Keep coworker orchestration one level deep and behind one facade. The parent
  worker receives no Plan scheduler or arbitrary main-to-worker transport role.
- Reuse the existing endpoint validator for parent and root coordinator. Expose
  the root endpoint only to terminal status delivery, not the generic message
  CLI.
- Persist relative writable paths in the coworker instruction and render them in
  its immutable contract; an empty list means review-only.

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
- Base64-encoding the full contract in `developer_instructions`: shell-safe but
  unreadable to the model without another decoding mechanism.
- A full nested Plan: adds scheduling and cleanup authority when the requested
  model is only one parent worker bringing one colleague alongside it.

## Risks and verification seam

Source authentication depends on live Herdr pane identity; headless status keeps
its compatibility path. Sentence detection is intentionally a guardrail, not a
linguistic parser; messages without terminal punctuation count as one sentence.
Pane split responses are validated for both `pane_id` and same-tab `tab_id`; a
missing or mismatched identity fails before provider start.
Coworker creation is tested through the facade's public CLI with fake Herdr;
Codex argument safety also gets a real Herdr probe because fake subprocesses
cannot reproduce target-shell encoding.
Public CLI tests are the primary seam because they cover argument parsing,
endpoint resolution, body/reference validation, envelope construction, and
persisted proof together.
