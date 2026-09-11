---
name: reporting-to-user
description: Use when a main agent closes out finished work to the user.
---

## Grade what surfaced

Open with the outcome: what is terminal, its completion reference, and its
review disposition. Grade everything else that surfaced into one level, by its
consequence for the user's work.

- **Alert** — act now. A failed or blocked task, an anchor whose checkpoint was
  never exercised, a landed change with unresolved review findings, exposed
  credentials or production state, or a dependent task left blocked.
- **Warn** — carry knowingly. Scope the work left out, evidence weaker than the
  named anchor, a deviation from the user's terms, or a limitation of the
  delivered result.
- **Info** — informational. Completed items, evidence references, and incidental
  facts.

## Write it compactly

Report Alert first, then Warn, then Info.

Info is a bullet list, one line each. Each Warn and Alert finding gets one line
naming the finding, its evidence reference, its concrete consequence, and the
follow-up worth dispatching. Mixed results state what landed, what did not, and
what was left out.

## Resolve Alert and Warn

Ask the user whether to dispatch a follow-up, using the harness-native
ask-question interface. Present one decision at a time, Alert before Warn, and
wait for each answer; one decision covers several findings only when a single
follow-up resolves them all. Info asks nothing.

A declined follow-up is recorded with the user's decision and closed.

## Open the next round

Each accepted follow-up enters [boss-say](../boss-say/SKILL.md#route-the-work)
as a new round, carrying the finding, its evidence reference, and the outcome
the user asked for. Wrapped-up tasks stay wrapped up; the follow-up is new work
with its own graph, anchor, and lifecycle.

**Complete when:** every Alert and Warn finding holds a user decision, and each
accepted one has entered a new round.
