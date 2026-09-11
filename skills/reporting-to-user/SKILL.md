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

## Derive Next

**Next** is the recommendation list built from the Alert and Warn findings, and
the only level that asks the user anything. Each item names one concrete action,
the findings it answers, and the outcome it produces. Findings a single action
resolves become one item; a finding whose consequence the user already accepted
produces none.

Order Next by the findings behind it: Alert-derived items first, then
Warn-derived.

## Write it compactly

Report Alert, then Warn, then Info, then Next.

Info is a bullet list, one line each. Each Alert and Warn finding gets one line
naming the finding, its evidence reference, and its concrete consequence. Mixed
results state what landed, what did not, and what was left out.

## Resolve Next

Ask the user whether to dispatch each Next item, using the harness-native
ask-question interface. Present one item at a time in Next order and wait for
each answer. Alert, Warn, and Info ask nothing themselves.

A declined item is recorded with the user's decision and closed.

## Open the next round

Each accepted item enters [boss-say](../boss-say/SKILL.md#route-the-work) as a
new round, carrying the action, the findings behind it, their evidence
references, and the outcome the user asked for. Wrapped-up tasks stay wrapped
up; the follow-up is new work with its own graph, anchor, and lifecycle.

**Complete when:** every Next item holds a user decision, and each accepted one
has entered a new round.
