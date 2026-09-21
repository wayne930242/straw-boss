# Codex Jev renewal through resume

Start an opted-in Codex session in Herdr with `TYPESAFE_API_KEY` already exported:

```sh
STRAW_BOSS_JEV=1 codex
```

An unset, empty, or whitespace-only key silently retains ordinary renewal and
creates no Jev records. Keep activation out of shell startup files and global
configuration. Ordinary Codex and Claude behavior, including the renewal baseline
through 2026-09-25, stays unchanged. Claude's separate path is documented in
[Claude Jev pruning](jev-pruning.md).

## Renewal ordering

At the end of a turn above 200,000 input tokens, the Stop hook asks the session to
prepare its ordinary continuity payload. The detached deliverer waits for the
turn to end, then snapshots the live rollout and attempts Jev first. Successful
pruning continues through `codex resume` of a fresh candidate UUID in the same
Herdr pane. The candidate's history carries the work; the continuity payload is
reserved for fallback. Role priming and dispatch route adoption use the existing
renewal lifecycle.

The adapter uses shared [criteria](../config/jev-criteria.json) and
[policy](../config/jev-policy.json), including deterministic governing-input locks,
Codex recency pinning, 0.5 retention scores, and 300-character truncation. Live
Jev requests fit the production 25k-state / 30k-request estimated budgets.
Requests include exact target invocation/result content; long results are fully
covered in chunks, and the highest retention score across chunks preserves any
needed result. The
historical 32k regression judge and explicit copy command remain separate.

Two isolated, read-only Codex resumes measure baseline and candidate input. These
accounting requests use the source model/effort, disable task tools, and request
only `OK`; they add backend usage and latency. Both must report zero cached input
tokens and contain no tool call or additional compaction. The 10% gate uses the
larger of live source input and baseline probe input as its denominator. A gate
miss, unavailable measurement, Jev error, or preparation/storage failure selects
ordinary continuity renewal.

The native auto-compaction limit remains unchanged. A long turn, including the
turn preparing continuity, can reach native compaction before the detached
attempt starts; the adapter then evaluates that current compacted history.
New source work or a replacement renewal record supersedes an in-flight attempt
and keeps the active pane intact. Unsupported launch flags or an unavailable
pane identity also retain ordinary renewal.

## Records and recovery

The private Jev store contains one benchmark row per attempt, its lossless
original rollout and candidate rows, raw retention decisions, and isolated
accounting evidence. Files use 0600 and store directories use 0700. The configured
`STRAW_BOSS_HOME` relocates this store; ordinary renewal records retain their
existing location.

- `benchmark.jsonl`: backend probe counts, conservative gate percentage, Jev
  usage, fallback reason, and application status.
- `runs/<run_id>.json`: exact original rollout text and candidate rows, sufficient
  to reconstruct the original history without replaying tool actions.
- `requests/<run_id>.json`: original pane/session/process identity and supported
  launch options.
- `probes/<run_id>/`: isolated accounting rollouts and output. The temporary
  authentication copy is removed after each probe.

`decision: apply` records gate selection. `application.status: resumed` records
matching Herdr session/terminal identity and the candidate's persisted replacement
history after restart. The renewed session's Stop hook records actual input separately and marks
`application.status: verified` with `outcome: applied` when net reduction is
observed. Probe counts describe the isolated candidate, not actual subsequent
task input. Recovery and benchmark files can contain sensitive content
from earlier tool output; retain them in the user-private store.

The original live rollout is kept intact. A new private rollout file is registered
in the original Codex home's session catalog. The restart preserves supported
model, effort, profile, directory and permission options. A private Unix socket
carries the inherited launch environment in memory, so the TypeSafe key is not
placed in a shell command or a recovery record. If candidate startup fails after
exit, the deliverer attempts to resume the original session before ordinary
continuity renewal. A missing or changed foreground identity leaves the pane
intact and records an interrupted attempt for inspection.

See the [implementation verification](specs/2026-09-21-codex-jev-renewal-resume/verification.md)
for the exact tested runtime, observed branches and review disposition.
