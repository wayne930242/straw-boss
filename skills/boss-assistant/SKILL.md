---
name: boss-assistant
description: Use when named by the user or when a main agent reports Straw Boss coordination friction.
---

## Resolve the recipient

Read the directory through [contacting-orchestrators](../contacting-orchestrators/SKILL.md). A live scope starting with `[boss-assistant]` identifies the assistant. Route a report to the existing assistant; with several, use the user's selection or ask which one. If none exists, ask whether this session should take the role unless the user already named it.

Register the selected session:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/register-orchestrator.py" \
  --scope '[boss-assistant] coordinate main agents on Straw Boss friction and graph repair'
```

Use [handoff-orchestrator](../handoff-orchestrator/SKILL.md) when a separately approved user window is needed. Keep a report's blocked step pending until its recipient is reachable; independent work can continue.

## Repair the coordination relationship

A report states expected versus actual behavior and the blocked step; references carry the task/plan, running version, reproduction, and evidence. Acknowledge its message id and combine reports with the same evidenced root cause.

Identify the owner and the relationship blocking progress: registration, endpoint, dependency, shared resource, checkpoint, or cleanup. Accept each task owner's work conclusions and verify the coordination state needed for the repair. Apply mutations serially through their owners using [dispatching-work](../dispatching-work/SKILL.md), [contacting-orchestrators](../contacting-orchestrators/SKILL.md), or [handoff-orchestrator](../handoff-orchestrator/SKILL.md). User-owned conflicts return to the user while current direction stands.

Read back the repaired state and have the reporting main agent exercise its blocked step and next handoff. Attach the result to the report; distinguish executable tests from the actual UAT outcome. Report on state changes or user questions.

## Carry a source finding

Locate a Straw Boss checkout from cwd, the orchestrator directory, or configured apps. Confirm its git root and remote and read local instructions and working-tree state. The installed cache identifies the running version; the confirmed checkout owns source edits.

Carry the finding and reproduction into `leveraging-tasks`, which owns design, implementation, and verification. For performance or storage friction, carry a relevant baseline, affected ownership/recovery contract, and the same workload for comparison. Return the measured result and actual UAT outcome to the reporting agents, including whether the running version contains the repair.

Prepare an issue or PR draft from the confirmed evidence. Resolve upstream from the checkout remote or installed manifest, check accessible existing reports for duplicates, and remove credentials/private task content. With no checkout, retain an issue draft and ask for a location only if needed for a repair. Once reviewable, resolve the user's publication decision; an authorized publication includes its required feature-branch push. Read back the published URL and content.

**Complete when:** each report is restored or has an owner, blocker, and next event; repair evidence is attached; each proposal has a published result or local draft location. Preserve undelivered replies and report their delivery failure.
