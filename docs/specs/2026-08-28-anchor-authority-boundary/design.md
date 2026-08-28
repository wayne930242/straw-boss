# Anchor authority boundary design

## Why scoping, not moving

Two repairs could remove the contract conflict: move the anchor to the worker,
or narrow what the contract's "verification method" covers. The user owns this
call and chose the second — the anchor category and its checkpoint are
scheduling facts a coordinator needs before it can claim a port, size a wave, or
arrange a review agent, while the seam, cases, and tooling are work definition.

So the boundary is cut at **category versus method**, and stated once in
`docs/roles.md` under Authority boundary. Every other surface carries the same
scope inline rather than a pointer, because two of them — the generated contract
and the SessionStart stance — arrive in a session that has no `docs/roles.md` in
context. The line "Naming the anchor is not naming the tests" is the short form
that makes the split legible in both.

`7c00f06`'s own repair of this conflict was to add "or the reality anchor" to
`dispatching-work` Task 3's allowed-brief list — an exception that let the
contradiction stand. That clause is gone; the verification now asks the opposite
question, whether the brief prescribed the method inside the anchor.

## Graph taxonomy

The original adoption conditions keyed `orchestrator-worker` on workflow
stability ("what the next task should be depends on what the last one found") or
a concurrency cap. `work-on`'s plan path is neither: its dependency graph is
confirmed with the user through `grilling`, and `dispatching-work` dispatches a
ready wave with no cap. The flagship multi-task path could not name a graph.

Re-keying on *how many app-rooted workers run under one loop, and by what
mechanism* fixes that and two others at once. `single-loop` no longer says
"nothing else is scheduled against it", so it stops contradicting the rule that
every ordinary programming change carries an independent review. And
`orchestrator-worker` no longer needs the "coordinator's shape alone" red line:
a worker brings at most one coworker with no nesting, so it cannot structurally
reach that shape. A derivable fact does not need a prohibition.

## Read-only anchoring

Making `adversarial-review` mandatory-as-anchor whenever the other three offered
no checkpoint forced a second agent onto every audit and research dispatch, at
no notice to the two skills that own those dispatches. The general rule now
matches the user's own permissive phrasing — adversarial review *may* serve as
the anchor — but read-only work keeps a mandatory one, because nothing else is
on offer: `choosing-graph` still reads "adversarial-review is its anchor". So
the cost H named is unchanged. What changed is that the skills owning those
dispatches state it in their own deliverable paragraph instead of inheriting it
silently from another file.

A first attempt named the evidence references themselves as the anchor for
read-only work. That fails under this boundary: the main agent names an anchor
from a closed list, and "evidence references" is not on it, so an audit dispatch
would have had no nameable category — the same defect shape as A, reintroduced
by the repair for H. The set stays at four. Read-only work is anchored on
adversarial review, and the evidence references are named as what that review
attacks, which is the part the two skills genuinely needed to know.

## Port reason and release

The stated reason a worker skips the claim was wrong. It cited the self-probe
caveat, whose premise is a server already bound — but the worker skips the claim
*before* starting anything, when nothing is listening. Following the stated
reason would authorize the exact re-claim the rule exists to prevent. The real
mechanism is the lock: `acquire` has no holder-identity short-circuit, so the
same holder contends with itself and walks on.

The release lived only in `shipping-task` Task 6, which `boss-say`'s batch path
never reaches, and in a plan auto-detach clause conditioned on
`failed`/`cancelled`. The rule now lives once in
`shared-resource-coordination.md` and both terminal paths point at it, which is
the single-source-of-truth pattern `7c00f06` already applied to the port
mechanics themselves.

## Test strategy

The eight tests `7c00f06` added asserted that a phrase appeared in one file.
None of them could fail on a contradiction between two files, which is the whole
risk surface of a change like this. The replacements are built to fail on that:

- The authority test builds a **real contract** from
  `dispatch_state.render_dispatch_contract` and requires every sentence granting
  a verification method — in the contract and in every prose surface — to carry
  the anchor scope, plus a floor on how many such grants exist so the test
  cannot be satisfied by deleting them.
- Graph names, lifecycle-mode names, and retired vocabulary are checked across
  every live surface at once, including `CONTEXT.md` and `scripts/`.
  `_Avoid_:` lines are excluded, because a glossary has to be able to name what
  it retires.
- The release rule is checked as a link: the rule text plus both terminal paths
  pointing at it, not one string in one file.
- `claim-port`'s command block is required to appear in exactly one file.
- The port reason is pinned by executing `claim-resource.py`: same holder, same
  key, nothing listening, second claim lands on a different port. This one
  cannot go red on the pre-fix tree — the script was never wrong, the prose was
  — but it fails the day someone adds a holder short-circuit that would make the
  documented reason false.
