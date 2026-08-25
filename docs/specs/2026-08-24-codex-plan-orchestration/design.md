# Codex Plan orchestration design

> Historical record. Live transport design is superseded by
> `docs/specs/2026-08-25-dispatched-agent-lifecycle-transport/`.

## Chosen approach

Use the existing dispatch instruction and status command as the
provider-neutral reachability seam:

1. `dispatch-task.py` records both `agent_kind` and `main_agent_kind`, validates
   the offered reachability capabilities, and accepts either supported agent
   kind for a Plan task.
2. `report-task-status.py --instruction-path` remains the single worker-facing
   status interface. It writes status first and then invokes `herdr agent
   prompt` when the instruction offers a main-agent pane.
3. A new `watch-plan-status.py` watches status *content revisions* and emits a
   structured event on every transition; Plan wave scheduling reacts to those
   events and then calls the existing `read-plan-status.py --ready` interface.
4. `reply-to-worker.py` resumes any supported interactive herdr agent. Codex
   transcript reads use the already-supported visible-screen fallback.
5. Provider-specific communication is additive: `SendMessage` is allowed only
   for Claude-to-Claude dispatches and is a fallback, never the primary
   cross-session path. Codex correctness never depends on it.
6. `asking-peer-agents` applies that same adapter order laterally: prompt the
   recorded peer pane first for Claude or Codex, and resolve a Claude peer name
   only for a Claude-to-Claude fallback.

## Interfaces and data flow

```text
dispatched agent
  -> report-task-status.py
     -> plans/<slug>/status/<task>.json
     -> herdr agent prompt <main-agent pane> (when recorded)
  -> watch-plan-status.py event (durable recovery and scheduling)
  -> main agent calls read-plan-status.py --ready
  -> dispatch-task.py writes the newly ready task
```

The instruction's `main_agent_kind`, `main_agent_herdr_pane_id`, and optional
`main_agent_send_message_peer` describe receiver capabilities rather than
inferring them from the worker kind. The herdr adapter is executable from both
supported agent CLIs. The SendMessage adapter remains a Claude tool call and is
therefore exposed only when both endpoints are Claude.

Peer questions use the target dispatch instruction as the equivalent receiver
capability record: `agent_kind` identifies its provider and `herdr_pane_id`
addresses its pane. This keeps vertical reports and lateral questions on the
same transport invariant without merging their authority rules.

The watcher accepts `--plan`, `--poll-interval`, and `--once`. Internally its
stable test seam is `collect_status_changes(plan_slug, seen_revisions)`, where a
revision is derived from complete file content. A new watcher starts with an
empty revision map, so persisted statuses are re-emitted for recovery.

## Alternatives considered

### Keep status writing and live notification as separate worker steps

Rejected. It leaves every worker prompt responsible for remembering ordering and
transport selection, which is the observed failure. Extending the existing
status interface keeps the invariant local: durable state exists before any
best-effort live prompt.

### Keep `SendMessage` primary and build a Codex messaging bridge

Rejected. Codex has no Claude `SendMessage` identity. The supported seam is the
existing herdr pane shared by both providers, not an emulated Claude mailbox.

### Only remove the non-Claude guard

Rejected. Codex could write a final status, but checkpoint-to-terminal changes
would still be missed and the main agent could remain unaware. This passes the
happy path while retaining the original reliability defect.

## Locality and compatibility

Provider variation stays behind instruction validation and the existing status
command; the dependency graph and status schema do not branch by provider.
Removing this seam would redistribute provider-pair checks and write-before-send
ordering into every dispatch prompt, so the interface has real leverage rather
than being a pass-through.

## Risks

- A worker can still violate its instruction and omit the status write.
  Dispatch/process completion checks must treat a missing terminal record as a
  failed/unreported task, not infer success.
- A herdr prompt can fail after persistence. The command reports failure without
  rolling back durable state; the watcher remains authoritative for Plan
  recovery, and only a Claude-to-Claude pair may fall back to `SendMessage`.
- Status files are single-writer per task, but a watcher may read during a
  write. The watcher tolerates transient invalid JSON and retries.
- Existing active OpenSpec changes describe Claude-specific push behavior; all
  canonical and active deltas touched by this contract must be reconciled.

## Verification surface

The public script CLIs, fake-herdr boundary, and status files are the primary
test surface. Focused tests prove provider-pair validation and status-before-send
ordering, followed by the full unittest suite, `openspec validate --all
--strict`, Python compilation, and a repository-wide contradiction scan.
