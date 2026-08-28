# Deliver the adversarial-review obligation design

## The carrier follows the rule's shape

The anchor lives in the free-text brief because it **varies** per dispatch. The
adversarial-review obligation does not vary — it holds for every ordinary
programming change, always. Putting an invariant rule in a per-dispatch brief
inherits the exact failure the last round patched for the anchor: the main agent
omits it, nothing else carries it, and no honest degradation exists either,
because a worker cannot usefully ask "am I obligated?" when the answer is
always yes.

So the obligation goes where nothing can drop it: a standing bullet in the
generated contract every dispatched session reads. It is self-limiting — it
names the dispatches it covers, so a read-only dispatch (where adversarial
review is already the anchor) and a review-only coworker read past it.

`shipping-task` is not the delivery path; it is the **coordinator-side
acceptance**. Task 4 states the rule where the skill that owns every ordinary
programming change can be seen to know it — H's complaint, for the skill H's
own repair never reached — and Task 6 confirms the review actually ran against
the confirmed commit or merge reference and dispositions what it reports.

The brief keeps one job here: saying who runs the review, and only when that is
not the worker. The contract states the default; the brief overrides it. That is
one sentence in each, not a mechanism.

`shipping-task` is not the only path a change takes, so it is not the only
acceptance point. `boss-say`'s capped batch dispatches its items through
`dispatching-work` Tasks 1-5 directly and closes them out in its own Task 7,
never reaching `shipping-task` Task 6. Both wrap-ups carry the disposition, and
`choosing-graph` names both — a rule that named one while two paths land changes
would be the defect class this change exists to close.

## Two routes, because two routes are already in use

`choosing-graph` assigned the action to the worker alone: "The worker reaches
for it through its own `Agent` tool or `bringing-coworker`." This repo's own
practice is the other route — the coordinator dispatches an independent review
against the committed result, which is how `7c00f06`, `969e0bd`, and `cc690f3`
were each reviewed, and how this change is reviewed too.

Writing the acceptance condition against the worker's route alone would have
made this very change fail its own new rule on arrival — the same class of
defect (a declaration its target does not support) the last two rounds exist to
close. So the rule names both routes and the acceptance condition is true of
either. Naming who acts is not widening the worker's grant: the category and
its checkpoint stay the coordinator's, and nothing here touches the method
inside the anchor.

## The fallback is not a transport rule

`cc690f3` put "ask the main agent to name the anchor when this dispatch does
not" inside the bullet that opens "In `herdr-pane`, you are an independent agent
after launch." `render_dispatch_contract` takes no mode, so a headless worker
reads the same sentence under a condition that excludes it.

The mode scoping is right for the half it was attached to — "you and the user
choose" needs a user in the loop, and `claude-p` has none. The fallback is a
worker-to-main action that needs no user at all. So the bullet splits: the
mode-scoped half stays, and the anchor-authority half becomes its own
unconditional bullet.

That leaves one thing to keep executable. A `claude-p` worker cannot wait for a
reply, so "ask the main agent" has to name an action it can actually take: the
`awaiting-main-agent` checkpoint, which persists first and then notifies,
whether or not the session survives to read an answer.

## Scope the universal, do not add a source

Task 3's Verification opened with a universal over *every* brief statement and
then required, in the next clause, a statement none of its three sources can
produce: the anchor is a decision the dispatch makes, not a fact the main agent
already held.

Adding a fourth source ("a coordination decision this dispatch made") would
restore the deleted exception under a new name and falsify
`close-rereview-findings/design.md`'s "Nothing is lost by removing it". The
universal is instead scoped to what it actually governs — every brief statement
**about the work** — and the coordination the dispatch fixed is stated as the
brief's own element. The allowed-source list is unchanged and still does not
mention the anchor.

## Both coordination decisions, where authority is defined

`docs/roles.md` calls itself the single execution-time definition of who decides
what, and `choosing-graph` calls the graph and the anchor **both** coordination.
Only the anchor was defined there, and `i-am-orchestrator` — the one surface a
SessionStart hook guarantees a main agent reads — listed only the anchor too. A
main agent that never opens `choosing-graph` received one of the two decisions
it owns. Both files now carry both.

## Precedence, not a wider tie-break

`close-rereview-findings/design.md` argued against extending the two-way
tie-break to three graphs, and that argument holds: a mixed batch running one
item in a subagent must not read as fan-out when it still writes a `plan.json`.
It also asserted the `orchestrator-worker` boundary was "already decided
cleanly" without writing the decision down.

This is that decision, written down, as a separate rule rather than a wider
tie-break: more than one app-rooted worker under one coordination loop is
`orchestrator-worker` whatever else runs beside it. The pair tie-break keeps its
scope, its paragraph, and its exemption for the anchor's own check.

## Titles are pointers

`cc690f3` widened the release paragraph to a second lock that is not a
dispatch-time claim, and left the title reading "Releasing a dispatch-time
claim" — which is also the string both pointers use to locate it. The title
moves to what the paragraph now releases, and both pointers move with it.

## Test strategy

Every fix that changes a live instruction surface is pinned by a test that fails
on the defect:

- The contract tests split the real `render_dispatch_contract` output into
  top-level bullets, because scope in that file is positional: the same sentence
  inside the `herdr-pane` bullet and in its own bullet are different rules.
- The obligation test requires exactly one standing bullet, requires it to name
  which dispatches it covers, and requires it to name no transport.
- The `shipping-task` test requires the statement and the acceptance condition.
- The brief test requires the scoped universal and the brief's own element.
- The precedence test extracts the paragraph and requires it not to contain the
  pair tie-break, so the two rules cannot merge back into one.
- The supersede test reads the *superseding* spec's claim, resolves the spec
  directory it names, and requires a forward marker there — so it fails on the
  disagreement rather than on a missing phrase.

The two narrative corrections carry no test, on the precedent
`close-rereview-findings/verification.md` set: a test asserting a docstring or a
disposition-table sentence pins the wording, not the fact.
