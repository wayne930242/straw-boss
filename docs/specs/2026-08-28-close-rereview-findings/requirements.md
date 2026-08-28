# Close the re-review findings requirements

## Outcome and actors

An independent adversarial re-review of `969e0bd` confirmed that its repair was
substantive — A through I and m1–m5 all closed — and found six new findings plus
four record-level inaccuracies. None of them is a design contradiction. They are
one class: **a record, a pointer, or a declaration that its own target does not
support.** Three records state a deletion the diff never made; the generated
contract asserts a fact about the dispatch that nothing carries; a wrap-up step
claims coverage the paragraph it points at denies; the glossary retires a phrase
the plugin is still using in another sense.

All six fell outside the test suite's sampling boundary, so the suite could not
have caught any of them.

Actors are the user, the main agent, the dispatched worker, the generated
contract both sides read, and the spec records a later reader will treat as
fact.

## In scope

- `dispatching-work` Task 3's allowed-source list, and the three records that
  describe it.
- The generated contract's unconditional claim that the dispatch names an
  anchor, when the anchor lives only in free-text and can be absent.
- The Wrap-up release step, the paragraph it points at, and that step's own
  acceptance condition.
- `CONTEXT.md`'s collision between a retired coordination alias and a live term
  of a different meaning.
- `troubleshooting-app`'s anchor on each of its two branches, and
  `choosing-graph`'s read-only rule naming a whole skill instead of the branch
  it applies to.
- A tie-break for the two coordination graphs that both fit the same situation.
- Record corrections in `2026-08-28-anchor-authority-boundary`: the red-set
  labels, the H narrative, and the reconciliation note's second spec.
- The test suite's sampling boundary, written down where it is set.

## Out of scope

- A structured anchor field in the instruction JSON or `dispatch-task.py write`.
  A field only moves the same free-text judgment behind an argument, and the
  prose carrier already exists; the gap is what the contract says when the
  anchor is missing.
- Editing the dated records of earlier changes. A superseded record keeps its
  era's wording; only a misreported measurement is corrected in place.
- Treating `_Avoid_` as a global word ban. It retires a name for one concept,
  and "subagent", "model", and "role" are each retired for one concept and live
  for another.

## User-owned decisions carried into this change

1. Correct directly. No new exception clause, red line, or defensive caveat is
   added to cover a finding.
2. Reality anchor `testing`; the layer inside it is unit-level tests over the
   prose and the generated contract, in `tests/`, each red before its fix.
3. Coordination graph `single-loop`, solo-mode on a clean `main`, committed
   without a push.
