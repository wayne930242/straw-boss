# Anchor authority boundary requirements

## Outcome and actors

`1da9e55` and `7c00f06` introduced the coordination graph and the reality anchor
without an accompanying spec, and an independent adversarial review found nine
findings plus five minor ones. The severe one is an authority conflict: the
generated dispatch contract — mandatory, hashed, injected before a worker's
first turn — grants the worker and user the **verification method**, while the
new skills had the main agent fix the **reality anchor** and hand it down. A
worker received two instructions and no rule for which one wins.

Actors are the user, the main agent, the dispatched worker, and the generated
contract that both sides read.

## In scope

- The authority boundary between naming a reality anchor and choosing the
  method inside it, stated once and carried by every surface that grants either.
- The coordination-graph taxonomy: an adoption criterion that covers every
  dispatch path this plugin actually runs, with no category that contradicts
  another rule.
- The reality-anchor rules: the human anchor's own self-contradiction, the
  read-only (audit/research/diagnosis) path's missing anchor, and the cost that
  path was silently absorbing.
- The dispatch-time frontend port: the stated reason a worker does not re-claim
  it, and a release point that every terminal path reaches.
- Regression coverage that can fail on a cross-file or behavioural
  contradiction, replacing eight assertions that only checked whether a phrase
  was present in one file.

## Out of scope

- `scripts/claim-resource.py` behaviour. It is unchanged; the repair is to the
  prose that described its mechanism incorrectly.
- The lifecycle-mode question itself. `team-mode`/`solo-mode` remains the user's
  reading of the work, not a size judgment.
- Any new anchor category. Read-only work is anchored by the evidence its own
  skill already requires; naming that role is not adding a fifth bullet.

## User-owned decisions carried into this change

The user reaffirmed these before the repair landed, and they bound the design:

1. `team-mode`/`solo-mode` follows how the user regards the work.
2. A dispatch plan belongs to `orchestrator-worker` alone; the other two graphs
   write none.
3. Ordinary programming work carries an independent agent's adversarial review,
   and that review **may** serve as the anchor when no other one fits.
4. A human reading code or a document is review, never the anchor.
5. A frontend human/pseudo-human check gets its port assigned at dispatch.
6. Skills stay lean, clear, contradiction-free, and free of meaningless
   defensive clauses or red lines.
7. The main agent decides the anchor **category** and its checkpoint
   arrangement; the worker and user decide the verification method **inside**
   that category — for testing, unit by default, escalated to integration or
   E2E on the target project's own conventions.
