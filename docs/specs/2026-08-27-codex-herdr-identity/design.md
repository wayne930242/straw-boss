# Codex Herdr identity design

## Chosen approach

Deepen the existing `dispatch_transport.py` seam with provider-specific endpoint
fingerprints:

```text
Claude endpoint -> pane id + agent_session.value
Codex endpoint  -> pane id + terminal_id + agent kind
```

The launcher resolves the appropriate fingerprint after the first prompt and
writes it into the launch receipt. Confirmation copies it into the instruction.
Every semantic transport command continues to call the shared endpoint validator
without learning provider rules.

## Interfaces and data flow

- `dispatch-task.py write` records optional `session_id` and
  `herdr_terminal_id`, plus corresponding main/root coordinator fields.
- `launch-dispatched-agent.py` waits for a session only for Claude; Codex reads
  the live agent once and requires a terminal id and matching agent kind.
- The launch receipt adds `herdr_terminal_id`; its `session_id` is null for Codex.
- `dispatch-task.py confirm` preserves null and binds the provider-selected
  fingerprint.
- `Endpoint` carries optional expected session and terminal ids.
- `validate_live_session()` keeps its public name for compatibility but selects
  the provider-specific validator internally.
- Coworker derivation propagates both fingerprint fields and applies the same
  provider requirements.

## Local installation interface

`scripts/install.sh` is a zero-argument facade over the two provider adapters.
It discovers which supported CLIs are present, verifies that the source
manifests agree, then applies each CLI's native marketplace and plugin lifecycle.

- Claude: add the checkout as a user marketplace when absent; install when
  absent and update when present.
- Codex: add a local marketplace when absent; refresh an existing Git
  marketplace; add when absent and replace only a stale installed Straw Boss
  plugin because Codex has no plugin-update command.

The script verifies each adapter through its public `plugin list --json` result.
Provider-specific command and JSON differences stay behind this facade. The
alternative of documenting only two manual command sequences leaves update
semantics duplicated at every caller; a provider-selecting flag interface adds
burden without value because auto-detection already supports one-CLI systems.

## Initial task delivery confirmation

The transcript reader, whitespace-insensitive presence check, and bounded poll
move from `reply-to-worker.py` into the existing `dispatch_transport.py` seam.
Both reply delivery and initial launch reuse those primitives while retaining
their own send and state-transition rules.

The launcher appends a deterministic ASCII marker containing the task's full
SHA-256 digest, polls six times at two-second intervals for that marker, and
resends the same marked task once only after the first complete window finds no
marker. Keeping the proof at the prompt tail makes it observable in Herdr's
bounded transcript view even after a long task body scrolls away. Removing all
Unicode whitespace during comparison also tolerates CJK hard wraps. The receipt
is written only after a poll succeeds.

Alternatives rejected:

- Waiting for `agent_status == idle` is insufficient because the reported case
  was idle while the Codex input line was still empty, and provider startup
  screens do not share one stable state sequence.
- Comparing the complete rendered task cannot succeed when the task is longer
  than Herdr's bounded transcript view, and terminal rendering can insert spaces
  inside CJK text.
- A fixed startup sleep cannot prove delivery and either remains racy or adds
  unconditional latency.
- Duplicating the reply helper in the launcher would distribute provider-specific
  transcript rules and retry constants across two callers.

The executable seam is the public launcher CLI with fake Herdr: one case exposes
only a short transcript tail for a long task, while another keeps the first
prompt absent and exposes the retry. A focused CJK case protects the shared
whitespace-insensitive matcher. Existing reply-to-worker tests protect the
extracted helper's prior behavior.

## Alternatives considered

### Store null and trust only the pane

Smallest change, but a provider replacement in the same pane would be accepted.
It also leaves the instruction unable to distinguish the Herdr terminal instance.

### Use the Codex thread id

Correct for provider-native resume, but Herdr 0.8.0 does not expose it through
`agent start`, `agent get`, or `agent list`. Scraping terminal text or Codex
private storage would introduce a brittle adapter and conflate live routing with
resume semantics.

### Use foreground process-group id

Stronger process binding but less stable while the agent runs child commands.
The existing process-info fallback is suitable as corroboration, not the primary
long-lived Codex endpoint.

### Chosen terminal fingerprint

Herdr exposes it for every observed Codex agent, it remains stable for the pane's
terminal lifetime, and it combines with pane and agent kind without inventing a
provider thread id. The residual limitation is explicit: Herdr 0.8.0 cannot prove
the Codex conversation thread within the same terminal.

## Risks and controls

- `terminal_id` is not a Codex thread id. Naming and docs keep the concepts
  separate.
- Old Codex instructions lack this fingerprint. Live delivery fails closed and a
  fresh dispatch restores a complete identity.
- Provider replacement in the same terminal could retain `terminal_id`; requiring
  `agent == "codex"` prevents cross-provider replacement but Herdr 0.8.0 cannot
  distinguish two Codex threads in one terminal. No stronger stable Herdr field is
  available.
- Claude behavior is protected by focused regression tests and retains its exact
  session check.

## Verification seam

Public CLI tests exercise fake `herdr agent start/get/prompt`, receipt JSON,
`dispatch-task.py confirm`, coworker dispatch, and shared transport. Negative
terminal/provider mismatches prove fail-closed behavior. Full repository tests
and static checks follow.

Installer tests execute `scripts/install.sh` against stateful fake provider CLIs
and inspect their public calls and final reported versions. No separate human
appropriateness decision is needed for the command interface.
