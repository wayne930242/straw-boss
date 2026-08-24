# Codex Plan orchestration design

## Chosen approach

Use the existing Plan/status boundary as the provider-neutral seam:

1. `dispatch-task.py` accepts either supported agent kind for a Plan task.
2. `report-task-status.py` remains the single writer interface.
3. A new `watch-plan-status.py` watches status *content revisions* and emits a
   structured event on every transition; Plan wave scheduling reacts to those
   events and then calls the existing `read-plan-status.py --ready` interface.
4. `reply-to-worker.py` resumes any supported interactive herdr agent. Codex
   transcript reads use the already-supported visible-screen fallback.
5. Provider-specific communication is additive: Claude can also push through
   `SendMessage`; Codex correctness never depends on that unavailable channel.

## Interfaces and data flow

```text
dispatched agent
  -> report-task-status.py
  -> plans/<slug>/status/<task>.json
  -> watch-plan-status.py event
  -> main agent calls read-plan-status.py --ready
  -> dispatch-task.py writes the newly ready task
```

The watcher accepts `--plan`, `--poll-interval`, and `--once`. Internally its
stable test seam is `collect_status_changes(plan_slug, seen_revisions)`, where a
revision is derived from complete file content. A new watcher starts with an
empty revision map, so persisted statuses are re-emitted for recovery.

## Alternatives considered

### Keep `SendMessage` primary and build a Codex messaging bridge

Rejected. Codex has no Claude `SendMessage` identity, and emulating one would
couple Plan correctness to provider/session internals. It also would not repair
the existing filename-dedup bug.

### Only remove the non-Claude guard

Rejected. Codex could write a final status, but checkpoint-to-terminal changes
would still be missed and the main agent could remain unaware. This passes the
happy path while retaining the original reliability defect.

## Locality and compatibility

Provider variation stays at existing launch/resume communication boundaries;
the dependency graph and status schema do not branch by provider. Removing this
seam would redistribute provider checks into every scheduler caller, so it has
real leverage rather than being a pass-through.

## Risks

- A worker can still violate its instruction and omit the status write.
  Dispatch/process completion checks must treat a missing terminal record as a
  failed/unreported task, not infer success.
- Status files are single-writer per task, but a watcher may read during a
  write. The watcher tolerates transient invalid JSON and retries.
- Existing active OpenSpec changes describe Claude-specific push behavior; all
  canonical and active deltas touched by this contract must be reconciled.

## Verification surface

The public script CLIs and status files are the primary test surface. Focused
tests run first, followed by the full unittest suite, `openspec validate
--all --strict`, Python compilation, and a repository-wide contradiction scan.
