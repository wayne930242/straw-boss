---
name: reporting-to-user
description: Use when a main agent closes out finished work to the user.
---

## Grade what surfaced

Open with the outcome: what is terminal, its completion reference, and its review disposition.
Grade everything else that surfaced into one level, by its consequence for the user's work.

- **Alert** — act now: a failed or blocked task, an anchor whose checkpoint is still unexercised, a landed change with open review findings, exposed credentials or production state, or a dependent task left blocked.
- **Warn** — carry knowingly: scope the work left out, evidence weaker than the named anchor, a deviation from the user's terms, or a limitation of the delivered result.
- **Info** — informational: completed items, evidence references, and incidental facts.

## Derive Next

**Next** is the recommendation list built from the open Alert and Warn findings.
Each item names one concrete action, cites the findings it answers as `(Alert 1)` or `(Warn 2)`, and states the outcome it produces.
One action that resolves several findings is one item.
Order Next by the findings behind it: Alert-derived items first, then Warn-derived.
Sort each item into one of two kinds: a **user-owned decision** (a business rule, an authorization, or an external mutation) or an **execution choice** inside authorization the user already gave.

## Write it compactly

Report Alert, then Warn, then Info, then Next.
Number the items inside each level from 1; a Next item cites those numbers.
Every item is one line.
An Alert or Warn line names the finding, its evidence reference, and its concrete consequence.
A mixed result reports each part: what landed, what stalled, and what was left out.

## Resolve Next

Execution choices need no answer: they enter the next round directly, carrying the recommended action.
Gather every open user-owned item -- this round's and any still undecided from an earlier round -- and ask about all of them together, each with its context, its options, and a recommendation, using as many calls to the harness-native ask-question interface as its per-call question limit requires.
A harness without a multi-question interface gets one compact message listing every item together instead.
State explicitly when no user-owned item is open.
A declined item is recorded with the user's decision and closed.

## Open the next round

The execution choices and the accepted user-owned items enter [boss-say](../boss-say/SKILL.md#route-the-work) together as one round, each carrying its action, the cited findings, their evidence references, and the outcome the user asked for.

**Complete when:** every user-owned item holds a user decision, and the execution choices and accepted items have entered one new round.
