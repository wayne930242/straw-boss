---
name: choosing-graph
description: Use at the start of Straw Boss work, and when its coordination shape changes.
---

## Coordination graphs

State the graph before work starts, using the first matching case:

- **orchestrator-worker** — multiple app-rooted workers coordinated through status events, including capped batches and dependency plans.
- **sub-agent fan-out/fan-in** — independent work branches run in subagents and their caller integrates the results. Work needing the target app's own harness uses an app-rooted dispatch.
- **single-loop** — one bounded task carried by one agent, including coordination of one dispatch.

An independent review is a checkpoint, so it does not change the graph. A dispatched agent states its own graph for its task.

Only `orchestrator-worker` writes `~/.straw-boss/plans/<slug>/plan.json`, through [boss-say](../boss-say/SKILL.md#plan-and-schedule). The other graphs create no Straw Boss plan or repo-local spec. A dispatch's instruction, contract, and status under `~/.straw-boss/dispatch/` are lifecycle records, archived at wrap-up. The app's own development artifacts follow its local workflow.

## Reality anchors

The main agent names the anchor and checkpoint; the worker and user choose the verification method inside that anchor.

- **testing** — default for programming changes. Use the smallest credible seam that can go red before the change; escalate to integration or E2E according to the app's conventions.
- **pseudo-human** — a browser or computer operates the real interface, with screenshots and measurements as evidence.
- **human** — the user operates or judges the delivered artifact. Ask about pseudo-human only when the user's risk judgment is unresolved.
- **adversarial-review** — a fresh-context agent challenges the result against the requirement and evidence references. Use this for read-only work with no credible executable or operable checkpoint.

For frontend human or pseudo-human checkpoints, assign a reachable address through [shared-resource coordination](../dispatching-work/references/shared-resource-coordination.md#ports) before dispatch.

## Review checkpoint

Review one coherent programming change-set once, after implementation and primary verification. A fresh-context reviewer examines the finished change-set directly; correctness and contract findings return to the work loop, and nits receive an explicit disposition.

The lifecycle owner confirms the completion reference and records the review disposition against it. Reuse an existing disposition for the same change-set; changed code or unresolved findings reopen the relevant check. Dispatched work reaches this checkpoint through [wrap-up](../dispatching-work/SKILL.md#wrap-up); current-agent work through [shipping-task](../shipping-task/SKILL.md#complete-the-lifecycle).

**Complete when:** graph, anchor, and checkpoint are established; a completed programming change has its confirmed reference and review disposition.
