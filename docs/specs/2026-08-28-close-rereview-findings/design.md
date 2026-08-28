# Close the re-review findings design

## Delete the clause, not the records

Three records — `969e0bd`'s commit message, this spec family's `design.md`, and
its `verification.md` — state that Task 3's "or the reality anchor" allowed-list
exception was deleted rather than reworded. The diff appended a clause after it
and left it standing.

Two repairs were available: change the file, or change the two records that can
still be changed. Changing the file makes all three true at once, including the
commit message, which cannot be edited. It is also what the design intended: the
exception existed to let `7c00f06`'s contradiction stand, and once the boundary
is cut at category-versus-method there is nothing left for it to excuse.

Nothing is lost by removing it. The anchor is not an exception to the source
rule — it is a required element of the brief, so the following clause now says
the brief names *the anchor it settled on*. The clause states an obligation
where the list stated a permission.

## The contract degrades to the checkpoint

`render_dispatch_contract` asserts "the reality anchor this dispatch names".
Nothing carries the anchor structurally: `dispatch-task.py write` has no anchor
argument, the instruction schema has no field, and the anchor lives in the
free-text `--task`. The assertion can therefore be false on arrival — the
dispatch that produced the re-review naming this finding was itself an example —
and a worker reading it literally cannot tell how far its own verification
authority runs. Before `969e0bd` the grant was unconditional and complete; after
it, the grant is scoped to a referent that may not exist.

A structured field was considered and rejected. It relocates the same free-text
judgment behind an argument, and a main agent that would omit the anchor from
the brief omits the flag too — leaving the same gap plus a schema change.

So the contract says what to do when the referent is missing: *ask the main
agent to name the anchor when this dispatch does not.* That is the honest
degradation and it keeps the category where `docs/roles.md` puts it. The
alternative wording — the worker and user settle it themselves — would have
resolved the dangling reference by handing the worker the one decision the whole
boundary reserves for the coordinator.

## Narrow the paragraph, not the pointer

Wrap-up step 3 releases two locks: the one the main agent claimed at dispatch,
and any the worker reported claiming without confirming release. The paragraph
it points at opens "The worker never claimed this lock ... it has nothing to
report about it", which is true of the first and denies the existence of the
second.

The pointer is right and the paragraph is too narrow, so the paragraph moves:
"never claimed **the dispatch-time lock**", followed by the second case named
explicitly. Narrowing the pointer instead would have dropped a rule that
`969e0bd` had already removed from `shipping-task` Task 6 on the grounds that
the wrap-up branch now carries it.

The new step also gets an acceptance condition. A step with no verification
clause is a step the branch's own checklist cannot confirm.

## A term, not a rename

`dispatch shape` was registered as a retired alias of **coordination graph**
while `boss-say` uses it four times, including in its `description`, for a
different concept: how much work goes out at once, not how the agents are wired.
Both live in `boss-say` Task 1.

Neither side should move. The coordination graph is the newer, load-bearing
term; the dispatch shape is the name of a real decision this plugin makes and
renaming it would churn the skill index for nothing. So the glossary stops
retiring it and registers it as its own entry, which is what stops the collision
from returning as an unregistered term.

The wider finding — six of eight registered aliases have no guard — reads as a
coverage gap only until you notice what `_Avoid_` means. It retires a name *for
one concept*: "subagent" is retired as a name for the advisor and live as a name
for a subagent. A blanket scan would be red on the first line it read. The
guard that is meaningful is narrower: the three coordination entries retire
multi-word coordination phrases, and those have to be dead in `skills/`.

## The read-only rule reaches a branch

`choosing-graph` named `troubleshooting-app` alongside the two read-only skills,
but the skill is read-only only on its integration-preflight branch; its default
branch lands a fix. So the rule names that branch, and the skill states its
anchor on each: adversarial review of the account for the preflight, testing for
the fix — where the reproduction the worker establishes is what goes red.

That also repairs H's original complaint for the branch it still applied to: a
rule taking effect from a file the skill that owns the dispatch never mentions.

## One graph wins

The adoption criterion calls itself observable, but two bullets fit the same
situation: a coordinator driving one dispatch while running its own subagents
satisfies `single-loop` ("a coordinator driving a single dispatch's lifecycle
events is still this shape") and `sub-agent fan-out/fan-in` at once. The clause
that used to exclude this — "nothing else is scheduled against it" — was removed
by D's repair, correctly, with nothing put in its place.

The tie-break is the distinction the two bullets are already built on: whether a
branch of *the work itself* runs in a subagent. If one does, the shape is
fan-out. It sits in the same paragraph as the exemption for the anchor's own
check, because that exemption is the case the tie-break must not sweep in.

It adjudicates those two and stops there. `orchestrator-worker` is the boundary
with a mechanical consequence — it alone writes a `plan.json` — so a rule
reaching all three would make a mixed batch that runs one item in a subagent
read as fan-out while it still has to write a plan. Scoping the tie-break to the
pair that overlaps keeps the criterion meaning what it claims to mean without
disturbing the boundary that already decided cleanly.

## Test strategy

Each fix is pinned by a test that fails on the defect, not on a missing phrase:

- The allowed-list test reads the two records' claims *and* the sentence they
  describe, so it fails whenever a record and its tree disagree.
- The contract test builds the real contract through
  `render_dispatch_contract`.
- The release test extracts the target paragraph and requires both cases the
  pointer claims, plus the new step's acceptance condition.
- The vocabulary test parses `CONTEXT.md`, takes the aliases the three
  coordination entries retire, and scans every instruction line under `skills/`.
- The tie-break test requires the rule and the exemption in one paragraph.

`prose_surfaces()` now documents its own boundary. `docs` is scanned
non-recursively on purpose: `docs/specs/` and `docs/adr/` are dated records, and
a superseded ADR keeps its era's wording, so scanning them would report history
as drift. The findings closed here sat in exactly that blind spot, which is the
argument for writing the boundary down rather than widening it.
